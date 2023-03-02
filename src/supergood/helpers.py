from pydash import get, set_
from base64 import b64encode

import json
import hashlib

def hash_value(input):
    hash = hashlib.sha1()
    if not input:
        return ''
    if isinstance(input, list):
        encoded = json.dumps(input, sort_keys=True).encode()
        hash.update(encoded)
        return [b64encode(hash.digest()).decode('utf-8')]
    if isinstance(input, dict):
        encoded = json.dumps(input, sort_keys=True).encode()
        hash.update(encoded)
        return {'hashed': b64encode(hash.digest()).decode('utf-8')}
    if isinstance(input, str):
        encoded = input.encode()
        hash.update(encoded)
        return b64encode(hash.digest()).decode('utf-8')

def hash_values_from_keys(obj, keys_to_hash):
    for i in range(len(keys_to_hash)):
        key_string = keys_to_hash[i]
        value = get(obj, key_string)
        if value:
            set_(obj, key_string, hash_value(value))
    return obj

def safe_parse_json(input: str):
    try:
        return json.loads(input)
    except Exception as e:
        print(e)
        return input
