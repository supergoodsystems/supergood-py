import requests
import re
import pytest
from unittest.mock import patch, Mock

from pytest_httpserver import HTTPServer
from .helper import get_config
from supergood import Client
from supergood.api import Api

def test_ignore_redaction(httpserver: HTTPServer, mocker):
    config = get_config(ignore_redaction=True)
    mocker.patch('supergood.api.Api.post_events', return_value=None)
    mocker.patch('supergood.api.Api.post_errors', return_value=None)
    supergood_client = Client(config=config)
    httpserver.expect_request('/200').respond_with_json({ 'string': 'abc', 'number': 123, 'float': 123.45, 'bool': True, 'complex_string': 'Alex Klarfeld 911!'})
    requests.get(httpserver.url_for('/200'))
    supergood_client.flush_cache()
    supergood_client.kill()
    args = Api.post_events.call_args[0][0]
    body = args[0]['response']['body']
    assert body['string'] == 'abc'
    assert body['number'] == 123
    assert body['float'] == 123.45
    assert body['bool'] == True
    assert body['complex_string'] == 'Alex Klarfeld 911!'
