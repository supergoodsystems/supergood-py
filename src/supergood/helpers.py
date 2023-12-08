import gzip
import hashlib
import json
from base64 import b64encode
from urllib.parse import urlparse

from pydash import get, set_, unset
from pydash.arrays import flatten
from tldextract import extract

from .constants import DEFAULT_SUPERGOOD_BYTE_LIMIT, GZIP_START_BYTES


def hash_value(input):
    _input = input
    hash = hashlib.md5()
    if not input:
        return ""
    encoded = json.dumps(_input, sort_keys=True).encode()
    hash.update(encoded)
    return b64encode(hash.digest()).decode("utf-8")


def action_key(data, action):
    match action.lower():
        case "readact":
            return hash_value(data)
        case "hash":
            return f"<redacted>:{type(data).__name__}:{len(data)}"


def deep_set_(input, keypath, action):
    """
    input: a request or response json blob
    keypath: a keypath operating on an array, i.e. containing []
    action: the action to take on that value

    This function extends the `set_` function from pydash to operate
     on every entry in a series of potentially nested arrays

    Given input
    {
    "added":[
        {"type": "payment_instruments",
        "items": [
            {"type": "debit", "number": 12345},
            {"type": "credit", "number": 56789}
            {"type": "debit", "number": }
        ]
        },
        {"type": "bank_accounts",
        "items": [
            {"type": "savings", "number": 12345},
            {"type": "checking", "number": 54321}
        ]
        }
    ]
    }
    And key: `added[].items[].number`
    Will iterate through all (added, items) combinations to set the `number` field
    """
    all_keys = []
    for key_segment in keypath.split("."):
        print(f"this key segment {key_segment}")
        if key_segment.endswith("[]"):
            key_name = key_segment[0:-2]
            print(f"key name: {key_name}")
            if len(all_keys) == 0:
                arr = get(input, key_name)
                print(f"got array {arr}")
                for i in range(len(arr)):
                    all_keys += [key_name + f"[{i}]"]
            else:
                new_keys = []
                for keypart in all_keys:
                    arr = get(input, ".".join([keypart, key_name]))
                    for i in range(len(arr)):
                        new_keys.append(".".join([keypart, (key_name + f"[{i}]")]))
                all_keys = new_keys
            print(f"all keys: {all_keys}")
        else:
            all_keys = list(map(lambda k: ".".join([k, key_segment]), all_keys))
    print(all_keys)
    print(f"before: {input}")
    for key in all_keys:
        if action.lower() == "ignore":
            unset(input, key)
        else:
            set_(input, key, action_key(get(input, key), action))
    print(f"after: {input}")


def redact_values(
    input_array,
    remote_config,
    logger=None,
    ignore_redaction=False,
):
    remove_indices = []
    if ignore_redaction:
        return input_array
    for index, data in enumerate(input_array):
        print(f"on item {index}")
        url_extract = extract(data["request"]["url"])
        print(f"looking for {url_extract.fqdn}")
        for vendor_domain, endpoint_configs in remote_config.items():
            print(f"comparing to {vendor_domain}")
            if vendor_domain in url_extract.fqdn:
                # Matched vendor, check if this is a known endpoint
                print("matched, checking endpoints")
                for endpoint in endpoint_configs:
                    print(f"checking endpoint {endpoint}")
                    to_search = ""
                    print(f"pulling object from {endpoint.location}")
                    match endpoint.location:
                        case "path":
                            to_search = data["request"].get("path")
                        case "url":
                            to_search = data["request"].get("url")
                        case "domain":
                            to_search = url_extract.registered_domain
                        case "subdomain":
                            to_search = url_extract.subdomain
                        case "request_headers":
                            to_search = str(data["request"]["headers"])
                        case "request_body":
                            to_search = str(data["request"]["body"])
                    print(f"found {to_search}, applying regex {endpoint.regex}")
                    if endpoint.regex.search(to_search):
                        print("regex match, actioning")
                        # Matched endpoint. Check ignore and then sensitive keys
                        if endpoint.action.lower() == "ignore":
                            print("endpoint action is ignore, marking for removal")
                            remove_indices.append(index)
                            break
                        print("checking sensitive keys")
                        for key in endpoint.sensitive_keys:
                            print(f"checking key {key}")
                            key_split = key.key_path.split(".")
                            if key_split[0].startswith("response") and not data.get(
                                "response"
                            ):
                                # None/empty response object, move on
                                continue

                            parent_obj = None
                            match key_split[0]:
                                case "requestBody":
                                    parent_obj = data["request"]
                                    keypath = ".".join(["body"] + key_split[1:])
                                case "requestHeaders":
                                    parent_obj = data["request"]
                                    keypath = ".".join(["headers"] + key_split[1:])
                                case "responseBody":
                                    parent_obj = data["response"]
                                    keypath = ".".join(["body"] + key_split[1:])
                                case "responseHeaders":
                                    parent_obj = data["response"]
                                    keypath = ".".join(["headers"] + key_split[1:])
                            if parent_obj:
                                if "[]" in keypath:
                                    # Keys associated with arrays require iterating
                                    deep_set_(parent_obj, keypath, key.action.lower())
                                else:
                                    match key.action.lower():
                                        case "ignore":
                                            unset(
                                                parent_obj,
                                                keypath,
                                            )
                                        case "redact" | "hash":
                                            set_(
                                                parent_obj,
                                                keypath,
                                                action_key(
                                                    get(parent_obj, keypath),
                                                    key.action.lower(),
                                                ),
                                            )

                break  # Once we've matched a vendor and actioned on it we can break out
    if remove_indices:
        return list(filter(lambda ind, _: ind not in remove_indices, enumerate(data)))
    else:
        return data


def redact_string(input):
    redacted = ""
    for i in range(len(input)):
        c = input[i]
        if c.isupper():
            redacted += "A"
        elif c.islower():
            redacted += "a"
        elif c.isnumeric():
            redacted += "1"
        elif c.isspace():
            redacted += " "
        else:
            redacted += "*"
    return redacted


def redact_numeric(input):
    redacted = ""
    _input = str(input)
    for i in range(len(_input)):
        c = _input[i]
        if c.isnumeric():
            redacted += "1"
        elif c == "-":
            redacted += "-"
        elif c == ".":
            redacted += "."
    return redacted


def safe_parse_json(input: str):
    if not input or input == "":
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
