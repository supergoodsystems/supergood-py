import gzip
import json
import hashlib

from pydash import get, set_
from base64 import b64encode

from .constants import DEFAULT_SUPERGOOD_BYTE_LIMIT, GZIP_START_BYTES

def hash_value(input):
    _input = input
    hash = hashlib.sha1()
    if not input:
        return ''
    if isinstance(_input, list):
        encoded = json.dumps(_input, sort_keys=True).encode()
        hash.update(encoded)
        return [b64encode(hash.digest()).decode('utf-8')]
    if isinstance(_input, dict):
        encoded = json.dumps(_input, sort_keys=True).encode()
        hash.update(encoded)
        return {'hashed': b64encode(hash.digest()).decode('utf-8')}
    if isinstance(_input, str):
        encoded = _input.encode()
        hash.update(encoded)
        return b64encode(hash.digest()).decode('utf-8')

def redact_values(input, included_keys, ignore_redaction=False, byte_limit=DEFAULT_SUPERGOOD_BYTE_LIMIT):
    _input = input

    payload = get(_input, 'response.body')
    payload_size = len(str(payload))

    if(payload_size >= byte_limit):
        set_(_input, 'response.body', hash_value(payload))
        return _input

    if not _input:
        return ''

    if ignore_redaction:
        return _input

    if isinstance(_input, list):
        for i, ele in enumerate(_input):
            _input[i] = redact_values(ele, included_keys, ignore_redaction, byte_limit)
    elif isinstance(_input, dict):
        for key in _input.keys():
            if key not in included_keys:
                _input[key] = redact_values(_input[key], included_keys, ignore_redaction, byte_limit)
    elif isinstance(_input, bool):
        _input = False
    elif isinstance(_input, str):
        _input = redact_string(_input)
    elif isinstance(_input, int):
        _input = int(redact_numeric(_input))
    elif isinstance(_input, float):
        _input = float(redact_numeric(_input))
    return _input

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
        elif c == '.':
            redacted += "."
    return redacted


def safe_parse_json(input: str):
    if not input or input == '':
        return ''
    try:
        return json.loads(input)
    except Exception as e:
        return safe_decode(input)

def safe_decode(input, encoding='utf-8'):
    try:
        if isinstance(input, bytes) and input[:2] == GZIP_START_BYTES:
            return gzip.decompress(input)

        if isinstance(input, str):
            return input

        return input.decode(encoding)
    except Exception as e:
        return str(input)
