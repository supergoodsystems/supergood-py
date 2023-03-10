import pytest
import requests
import re

from pytest_httpserver import HTTPServer
from supergood import Client
from supergood.api import Api
from .helper import get_config

def test_hashing_single_field_in_body_from_config(httpserver: HTTPServer, mocker):
    config = get_config(keys_to_hash=['response.body.hash_me', 'response.body.i_dont_exist'])
    mocker.patch('supergood.api.Api.post_events', return_value=None)
    mocker.patch('supergood.api.Api.post_errors', return_value=None)
    supergood_client = Client(config=config)
    httpserver.expect_request('/200').respond_with_json({ 'hash_me': 'abc', 'dont_hash_me': 'def' })
    requests.get(httpserver.url_for('/200'))
    supergood_client.flush_cache()
    supergood_client.kill()

    args = Api.post_events.call_args[0][0]
    # Regex to match a base64 encoded string
    assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['hash_me']) is not None