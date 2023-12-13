import gzip
import hashlib
import json
from base64 import b64encode
from sys import getsizeof

from pydash import get, set_, unset

from .constants import ERRORS, GZIP_START_BYTES
from .remote_config import get_endpoint_from_config


def hash_value(input):
    _input = input
    hash = hashlib.md5()
    if not input:
        return ""
    encoded = json.dumps(_input, sort_keys=True).encode()
    hash.update(encoded)
    return b64encode(hash.digest()).decode("utf-8")


def get_with_exists(obj, key) -> tuple[any, bool]:
    """
    obj: a dictionary object, usually a request/response
    key: A keypath to test, in the form key1.key2[0].key3

    If the key path is valid, returns
    (value, True)
    otherwise returns
    (None, False)
    """
    dummy = object()
    test = get(obj, key, dummy)
    # If we get the default value back, the keypath does not exist
    if test != dummy:
        return test, True
    else:
        return None, False


def recursive_size(obj, seen=set(), include_overhead=False):
    """
    NB: NOT a perfect recursive sizeof. Expects it's operating on a JSON response
    By default does NOT include the overhead of dict overhead, just the sizes of keys and values
    """
    size = getsizeof(obj)
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    if isinstance(obj, dict):
        if not include_overhead:
            size = 0
        size = sum([recursive_size(v, seen) for v in obj.values()])
        size += sum([recursive_size(k, seen) for k in obj.keys()])
    return size


def action_key(data, action):
    """
    Performs the action defined in `action` on `data`
    Currently supports `redact` and `hash`. `ignore` handled upstream

    NB: The input is assumed to be a JSON blob. Only supports JSON types, not generic objects
    """
    match action.lower():
        case "hash":
            return hash_value(data)
        case "redact":
            typ = type(data).__name__
            match typ:
                case "NoneType":
                    return f"null:0"
                case "bool":
                    return f"boolean:1"
                case "str":
                    return f"string:{len(data)}"
                case "int":
                    return f"integer:{len(str(data))}"
                case "float":
                    return f"float:{len(str(data))}"
                case "list":
                    return f"array:{len(data)}"
                case "dict":
                    return f"object:{recursive_size(data)}"
                case _:
                    # It should be a json type, fail
                    raise Exception(ERRORS["UNKNOWN"])
        case _:
            # Unknown action type
            raise Exception(ERRORS["UNKNOWN"])


def deep_redact_(input, keypath, action):
    """
    input: a request or response json blob to be redacted
    keypath: a keypath operating on an array, i.e. containing []
    action: the action to take on that values at that keypath

    To redact a key that is present in one or many response array objects, e.g.
    `response.body.added[].payment_instruments[].number`
    you have to iterate over both (all) arrays to collect all the keys
    that need to be redacted.

    This function redacts (removes) all `keypath` keys in-place on `input`
    and returns metadata about each extracted key, which Supergood uses for schema
    anomaly detection.
    """
    all_keys = []
    for key_segment in keypath.split("."):
        if key_segment.endswith("[]"):
            key_name = key_segment[0:-2]
            new_keys = []
            for keypart in all_keys:
                arr = get(input, ".".join([keypart, key_name]))
                if arr is None:
                    # Key does not exist
                    continue
                for i in range(len(arr)):
                    new_keys.append(".".join([keypart, (key_name + f"[{i}]")]))
            all_keys = new_keys
        else:
            if len(all_keys) == 0:
                all_keys.append(key_segment)
            else:
                all_keys = list(map(lambda k: ".".join([k, key_segment]), all_keys))

    # Invariant: he first two elements of any keypath will always be
    #  of the form '{request|response}.{body|headers}'
    #  however for standardization we need to transform that to a single key
    #  '{request|response}{Body|Headers}'
    metadata = {}
    for key in all_keys:
        keysplit = key.split(".")
        actual_key = ".".join([(keysplit[0] + keysplit[1].capitalize())] + keysplit[2:])
        if action.lower() == "ignore":
            metadata[actual_key] = None
            unset(input, key)
        else:
            metadata[actual_key] = action_key(get(input, key), action)
            set_(input, key, None)
    return metadata


def redact_values(
    input_array,
    remote_config,
    ignore_redaction=False,
):
    """
    input_array: a dictionary, representing a `request, reponse` pair
    remote_config: the SG remote config

    """
    remove_indices = []
    if ignore_redaction:
        # add an empty metadata object to each one and return
        for i in range(len(input_array)):
            input_array[i].update({"metadata": {}})
        return input_array
    for index, data in enumerate(input_array):
        metadata = {}
        endpoint = get_endpoint_from_config(
            remote_config,
            url=data["request"].get("url"),
            request_body=data["request"]["body"],
            request_headers=data["request"]["headers"],
        )
        if endpoint:
            # Matched endpoint. Check ignore and then sensitive keys
            if endpoint.action.lower() == "ignore":
                remove_indices.append(index)
                break
            for key in endpoint.sensitive_keys:
                if key.key_path.startswith("response") and not data.get("response"):
                    continue
                key_split = key.key_path.split(".")
                match key_split[0]:
                    case "requestBody":
                        keypath = ".".join(["request", "body"] + key_split[1:])
                    case "requestHeaders":
                        keypath = ".".join(["request", "headers"] + key_split[1:])
                    case "responseBody":
                        keypath = ".".join(["response", "body"] + key_split[1:])
                    case "responseHeaders":
                        keypath = ".".join(["response", "headers"] + key_split[1:])
                    case _:
                        raise Exception("unknown keypath")
                if "[]" in keypath:
                    # Keys within an array require iterative redaction
                    redactions = deep_redact_(data, keypath, key.action.lower())
                    metadata.update(redactions)
                else:
                    item, exists = get_with_exists(data, keypath)
                    if not exists:
                        # Key not present, move on
                        continue
                    match key.action.lower():
                        case "ignore":
                            metadata[key.key_path] = None
                            unset(
                                data,
                                keypath,
                            )
                        case "redact" | "hash":
                            val = action_key(item, key.action)
                            metadata[key.key_path] = val
                            set_(data, keypath, None)
        if metadata:
            data["metadata"] = {"sensitiveKeys": metadata}
        else:
            data["metadata"] = {}

    if remove_indices:
        return list(
            filter(lambda ind, _: ind not in remove_indices, enumerate(input_array))
        )
    else:
        return input_array


def safe_parse_json(input: str):
    if not input:
        return ""
    try:
        return json.loads(input)
    except Exception as e:
        return safe_decode(input)


def safe_decode(input, encoding="utf-8"):
    try:
        if isinstance(input, bytes) and input[:2] == GZIP_START_BYTES:
            return gzip.decompress(input)

        if isinstance(input, str):
            return input

        return input.decode(encoding)
    except Exception as e:
        return str(input)
