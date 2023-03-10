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

@pytest.fixture(scope='session', autouse=True)
def supergood_client(session_mocker):
    config = get_config()
    # mock_api = mocker.patch('supergood.api.Api')
    session_mocker.patch('supergood.api.Api.fetch_config', return_value=config).start()
    session_mocker.patch('supergood.api.Api.post_events', return_value=None).start()
    session_mocker.patch('supergood.api.Api.post_errors', return_value=None).start()

    client = Client()

    yield client

    # mocker.patch('supergood.api.Api.fetch_config', return_value=config).stop()
    # mocker.patch('supergood.api.Api.post_events', return_value=None).stop()
    # client.close()

def test_captures_all_outgoing_200_http_requests(httpserver: HTTPServer, supergood_client):
    CALL_COUNT = 5
    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)

    for i in range(CALL_COUNT):
        response = requests.get(httpserver.url_for('/200'))

    supergood_client.flush_cache()

    args = Api.post_events.call_args[0][0]
    assert args[0]['request'] is not None
    assert args[0]['response'] is not None
    assert len(args) == CALL_COUNT

def test_captures_non_success_status_and_errors(httpserver: HTTPServer, supergood_client):
    http_error_codes = [400, 401, 403, 404, 500, 501, 502, 503, 504]
    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)

    for code in http_error_codes:
        httpserver.expect_request(f'/{code}').respond_with_data(status=code)
        response = requests.get(httpserver.url_for(f'/{code}'))

    supergood_client.flush_cache()

    args = Api.post_events.call_args[0][0]
    assert len(args) == len(http_error_codes)

    responded_codes = set(map(lambda x: x['response']['status'], args))
    assert responded_codes == set(http_error_codes)

def test_post_requests(httpserver: HTTPServer, supergood_client):
    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)
    httpserver.expect_request('/200', method='POST').respond_with_json({ 'payload': 'value' })
    response = requests.post(httpserver.url_for('/200'))
    response.raise_for_status()
    json = response.json()
    supergood_client.flush_cache()

    assert json['payload'] == 'value'
    args = Api.post_events.call_args[0][0]
    assert len(args) == 1

def test_post_request_for_large_payload(httpserver: HTTPServer, supergood_client):
    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)
    response = requests.post(URL, headers=HEADERS, json=PAYLOAD)
    response.raise_for_status()
    json = response.json()

    supergood_client.flush_cache()

    assert json.get("mapResults", {}).get("totalItems", 0) >= 0
    args = Api.post_events.call_args[0][0][0]
    assert args['request'] is not None
    assert args['response'] is not None

def test_hanging_response(httpserver: HTTPServer, supergood_client):
    HANG_TIME_IN_SECONDS = 2
    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)

    requests.get(f'{TEST_BED_URL}/200?sleep={HANG_TIME_IN_SECONDS}')
    supergood_client.flush_cache()

    args = Api.post_events.call_args[0][0]
    assert len(args) == 1

def test_posting_errors(supergood_client, session_mocker):
    config = get_config()
    _mock = session_mocker.patch('supergood.api.Api.post_events', side_effect=Exception('Test Error'))
    _mock.start()

    requests.get(f'{TEST_BED_URL}/200')

    supergood_client.close()
    error_message = Api.post_errors.call_args[0][2]
    assert error_message == ERRORS['POSTING_EVENTS']

    _mock.resetmock()
    session_mocker.patch('supergood.api.Api.post_events').start()


def test_different_http_library(httpserver: HTTPServer, supergood_client):
    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)

    http = urllib3.PoolManager()
    http.request('GET', f'{TEST_BED_URL}/200')

    supergood_client.flush_cache()

    args = Api.post_events.call_args[0][0]
    assert len(args) == 1

def test_aiohttp_library(httpserver: HTTPServer, supergood_client):
    async def aiohttp_get_request():
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{TEST_BED_URL}/200?success=true', headers=HEADERS, json=PAYLOAD) as response:
                return await response.json()

    async def aiohttp_post_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{TEST_BED_URL}/200?success=true', headers=HEADERS, json=PAYLOAD) as response:
                return await response.json()

    config = get_config()
    httpserver.expect_request('/api/config').respond_with_json(config)

    get_response = asyncio.run(aiohttp_get_request())
    post_response = asyncio.run(aiohttp_post_request())

    supergood_client.flush_cache()

    args = Api.post_events.call_args[0][0]
    assert len(args) == 2
    assert get_response['success'] == 'true'
    assert post_response['success'] == 'true'
    assert args[0]['response'] is not None
    assert args[0]['request'] is not None
