import unittest
import sys
import requests
import time
import re
import urllib3
import aiohttp
import asyncio
import json
import pytest

from urllib.parse import urlparse
from dotenv import load_dotenv
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from supergood import Client
from supergood.constants import ERRORS
from supergood.api import Api

from .helper import get_config
from .constants import *

load_dotenv()

TEST_BED_URL = 'http://supergood-testbed.herokuapp.com'

@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 0)

def test_captures_all_outgoing_200_http_requests(httpserver: HTTPServer, mocker):
    CALL_COUNT = 5
    config = get_config(httpserver)
    mocker.patch('supergood.api.Api.post_events')
    httpserver.expect_request('/api/config').respond_with_json(config)
    httpserver.expect_request('/200').respond_with_json({'payload': 'value'})
    client = Client(base_url=httpserver.url_for('/'))
    for i in range(CALL_COUNT):
        response = requests.get(f'{TEST_BED_URL}/200')
    client.close()

    args = Api.post_events.call_args[0][0]
    assert args[0]['request'] is not None
    assert args[0]['response'] is not None
    assert len(args) == CALL_COUNT

def test_captures_non_success_status_and_errors(httpserver: HTTPServer, mocker):
    http_error_codes = [400, 401, 403, 404, 500, 501, 502, 503, 504]
    config = get_config(httpserver)
    mocker.patch('supergood.api.Api.post_events')

    httpserver.expect_request('/api/config').respond_with_json(config)
    httpserver.expect_request('/200').respond_with_json({'payload': 'value'})

    client = Client(base_url=httpserver.url_for('/'))

    for code in http_error_codes:
        response = requests.get(f'{TEST_BED_URL}/{code}')

    client.close()
    args = Api.post_events.call_args[0][0]
    assert len(args) == len(http_error_codes)

    responded_codes = set(map(lambda x: x['response']['status'], args))
    assert responded_codes == set(http_error_codes)

def test_post_requests(httpserver: HTTPServer, mocker):
    config = get_config(httpserver)
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))
    mocker.patch('supergood.api.Api.post_events')

    response = requests.post(f'{TEST_BED_URL}/200?payload=value')
    response.raise_for_status()
    json = response.json()
    client.close()

    assert json['payload'] == 'value'
    args = Api.post_events.call_args[0][0]
    assert len(args) == 1

def test_post_request_for_large_payload(httpserver: HTTPServer, mocker):
    config = get_config(httpserver)
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))
    mocker.patch('supergood.api.Api.post_events')

    response = requests.post(URL, headers=HEADERS, json=PAYLOAD)
    response.raise_for_status()
    json = response.json()

    client.close()

    assert json.get("mapResults", {}).get("totalItems", 0) >= 0
    args = Api.post_events.call_args[0][0][0]
    assert args['request'] is not None
    assert args['response'] is not None

def test_hanging_response(httpserver: HTTPServer, mocker):
    HANG_TIME_IN_SECONDS = 2
    config = get_config(httpserver)
    httpserver.expect_request('/api/config').respond_with_json(config)
    mocker.patch('supergood.api.Api.post_events')

    client = Client(base_url=httpserver.url_for('/'))
    requests.get(f'{TEST_BED_URL}/200?sleep={HANG_TIME_IN_SECONDS}')
    client.close()

    args = Api.post_events.call_args[0][0]
    assert len(args) == 1

def test_posting_errors(httpserver: HTTPServer, mocker):
    config = get_config(httpserver)
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))
    mocker.patch('supergood.api.Api.post_errors')
    mocker.patch('supergood.api.Api.post_events', side_effect=Exception('mocked post events error'))

    requests.get(f'{TEST_BED_URL}/200')
    client.close()

    error_message = Api.post_errors.call_args[0][2]
    assert error_message == ERRORS['POSTING_EVENTS']

def test_hashing_entire_body_from_config(httpserver: HTTPServer, mocker):
    config = get_config(httpserver, keys_to_hash=['response.body'])
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))

    mocker.patch('supergood.api.Api.post_events')
    requests.get(f'{TEST_BED_URL}/200?hash_me=abc&dont_hash_me=def')
    client.close()

    args = Api.post_events.call_args[0][0]
    # Regex to match a base64 encoded string
    assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['hashed']) is not None

def test_hashing_single_field_in_body_from_config(httpserver: HTTPServer, mocker):
    config = get_config(httpserver, keys_to_hash=['response.body.hash_me', 'response.body.i_dont_exist'])
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))

    mocker.patch('supergood.api.Api.post_events')

    requests.get(f'{TEST_BED_URL}/200?hash_me=abc&dont_hash_me=def')
    client.close()

    args = Api.post_events.call_args[0][0]
    # Regex to match a base64 encoded string
    assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['hash_me']) is not None

def test_accepts_requests_to_non_ignored_domains(httpserver: HTTPServer, mocker):
    config = get_config(httpserver, ignored_domains=[])
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))

    mocker.patch('supergood.api.Api.post_events')
    requests.get(f'{TEST_BED_URL}/200')
    client.close()

    args = Api.post_events.call_args[0][0][0]
    assert f'{TEST_BED_URL}/200' == args['request']['url']

def test_ignores_requests_to_ignored_domains(httpserver: HTTPServer, mocker):
    config = get_config(httpserver, ignored_domains=['supergood-testbed.herokuapp.com'])
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))

    mocker.patch('supergood.api.Api.post_events')
    requests.get(f'{TEST_BED_URL}/200')
    client.close()

    Api.post_events.assert_not_called()

def test_different_http_library(httpserver: HTTPServer, mocker):
    config = get_config(httpserver)
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))

    mocker.patch('supergood.api.Api.post_events')
    http = urllib3.PoolManager()
    http.request('GET', f'{TEST_BED_URL}/200')

    client.close()

    args = Api.post_events.call_args[0][0]
    assert len(args) == 1

def test_aiohttp_library(httpserver: HTTPServer, mocker):
    async def aiohttp_get_request():
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{TEST_BED_URL}/200?success=true', headers=HEADERS, json=PAYLOAD) as response:
                return await response.json()

    async def aiohttp_post_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{TEST_BED_URL}/200?success=true', headers=HEADERS, json=PAYLOAD) as response:
                return await response.json()

    config = get_config(httpserver)
    httpserver.expect_request('/api/config').respond_with_json(config)
    client = Client(base_url=httpserver.url_for('/'))

    mocker.patch('supergood.api.Api.post_events')
    get_response = asyncio.run(aiohttp_get_request())
    post_response = asyncio.run(aiohttp_post_request())

    client.close()

    args = Api.post_events.call_args[0][0]
    assert len(args) == 2
    assert get_response['success'] == 'true'
    assert post_response['success'] == 'true'
    assert args[0]['response'] is not None
    assert args[0]['request'] is not None
