import gzip
import hashlib
import json
import sys
import traceback
from base64 import b64encode
from typing import Tuple

from pydash import get, set_

from .constants import ERRORS, GZIP_START_BYTES
from .remote_config import get_vendor_endpoint_from_config


def hash_value(input):
    _input = input
    hash = hashlib.md5()
    if not input:
        return ""
    encoded = json.dumps(_input, sort_keys=True).encode()
    hash.update(encoded)
    return b64encode(hash.digest()).decode("utf-8")


def get_with_exists(obj, key) -> Tuple[any, bool]:
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
    NB: Assumes it's operating on a JSON response. Not for general use
    By default does NOT include the overhead of dict overhead, just the sizes of keys and values
    """
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = 0
    if isinstance(obj, dict):
        if include_overhead:
            size += sys.getsizeof(obj)
        size += sum([recursive_size(v, seen, include_overhead) for v in obj.values()])
        size += sum([recursive_size(k, seen, include_overhead) for k in obj.keys()])
    else:
        size = sys.getsizeof(obj)
    return size


def describe_data(data):
    """
    data: a portion of a JSON response
    returns: a tuple describing the data: (type, length)
    e.g. describe_data("kazooie") => ("string", 7)

    for integers and floats uses the string length
    for dictionaries attempts to recursively determine the size (not including dictionary overhead)
    """
    typ = type(data).__name__
    if typ == "NoneType":
        return ("null", 0)
    elif typ == "bool":
        return ("boolean", 1)
    elif typ == "str":
        return ("string", len(data))
    elif typ == "int":
        return ("integer", len(str(data)))
    elif typ == "float":
        return ("float", len(str(data)))
    elif typ == "list":
        return ("array", len(data))
    elif typ == "dict":
        return ("object", recursive_size(data))
    else:
        # Expecting only JSON response types here. fail otherwise
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
            if not new_keys:
                # If at any step we run out of keys, this keypath must not exist anywhere.
                #  we can safely redact nothing and return
                return []
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
    metadata = []
    for key in all_keys:
        keysplit = key.split(".")
        if len(keysplit) == 2:  # to handle top-level redactions like responseBody
            actual_key = ".".join([(keysplit[0] + keysplit[1].capitalize())])
        else:
            actual_key = ".".join(
                [(keysplit[0] + keysplit[1].capitalize())] + keysplit[2:]
            )
        entry = get(input, key)
        (data_type, data_length) = describe_data(entry)
        # NB: The UI only supports `redact` for now, so the clients only support is as well
        set_(input, key, None)
        metadata.append(
            {
                "keyPath": actual_key,
                "type": data_type,
                "length": data_length,
            }
        )

    return metadata


def redact_values(
    input_array,
    remote_config,
    ignore_redaction=False,
):
    """
    input_array: a dictionary, representing a `request, reponse` pair
    remote_config: the SG remote config

    data is redacted in-place
    redaction info is placed in the metadata
    a list is returned indicating indices that should be removed
    """
    remove_indices = []
    if ignore_redaction:
        # add metadata if it doesn't exist, then return
        for i in range(len(input_array)):
            if "metadata" not in input_array[i]:
                input_array[i].update({"metadata": {}})
        return
    for index, data in enumerate(input_array):
        skeys = []
        endpoint = None
        if (
            ("metadata" in data)
            and (vendor_id := data["metadata"].get("vendorId", None))
            and (endpoint_id := data["metadata"].get("endpointId", None))
        ):
            endpoint = remote_config[vendor_id].endpoints[endpoint_id]
        else:
            _, endpoint = get_vendor_endpoint_from_config(
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
                top_level_array = key_split[0].endswith("[]")
                if key_split[0].startswith("requestBody"):
                    keypart1 = "request"
                    keypart2 = "body"
                elif key_split[0].startswith("requestHeaders"):
                    keypart1 = "request"
                    keypart2 = "headers"
                elif key_split[0].startswith("responseBody"):
                    keypart1 = "response"
                    keypart2 = "body"
                elif key_split[0].startswith("responseHeaders"):
                    keypart1 = "response"
                    keypart2 = "headers"
                else:
                    raise Exception(f"unknown keypath {key.key_path}")

                if top_level_array:
                    keypart2 += "[]"
                keypath = ".".join([keypart1, keypart2])
                if len(key_split) > 1:
                    keypath = ".".join([keypath] + key_split[1:])

                if "[]" in keypath:
                    # Keys within an array require iterative redaction
                    redactions = deep_redact_(data, keypath, key.action.lower())
                    skeys += redactions
                else:
                    item, exists = get_with_exists(data, keypath)
                    if not exists:
                        # Key not present, move on
                        continue
                    (data_type, data_length) = describe_data(item)
                    skeys.append(
                        {
                            "keyPath": key.key_path,
                            "type": data_type,
                            "length": data_length,
                        }
                    )
                    # NB: the only action supported for now is `redact`
                    set_(data, keypath, None)
        else:
            # No endpoint, potentially add metadata and move on
            if "metadata" not in data:
                data["metadata"] = {}
        if skeys:
            data["metadata"].update({"sensitiveKeys": skeys})
    return remove_indices


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
