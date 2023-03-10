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

# Hash values from specified keys, or hash if the bodies exceed a byte limit
def hash_values_from_keys(obj, keys_to_hash, byte_limit=DEFAULT_SUPERGOOD_BYTE_LIMIT):
    _obj = obj
    if 'response.body' not in keys_to_hash:
        payload = get(_obj, 'response.body')
        payload_size = len(str(payload))
        if(payload_size >= byte_limit):
            set_(_obj, 'response.body', hash_value(payload))

    if 'request.body' not in keys_to_hash:
        payload = get(_obj, 'request.body')
        payload_size = len(str(payload))
        if(payload_size >= byte_limit):
            set_(_obj, 'request.body', hash_value(payload))

    for i in range(len(keys_to_hash)):
        key_string = keys_to_hash[i]
        value = get(_obj, key_string)
        if value:
            set_(_obj, key_string, hash_value(value))
    return _obj

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
