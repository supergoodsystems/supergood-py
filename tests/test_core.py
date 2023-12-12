import asyncio
import json
import re
import sys
import time
import unittest
from urllib.parse import urlparse

import aiohttp
import pytest
import requests
import urllib3
from dotenv import load_dotenv
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from supergood import Client
from supergood.api import Api
from supergood.constants import ERRORS
from tests.constants import *
from tests.helper import get_remote_config

load_dotenv()

TEST_BED_URL = "http://supergood-testbed.herokuapp.com"


class TestCore:
    def test_captures_all_outgoing_200_http_requests(
        self, httpserver: HTTPServer, supergood_client
    ):
        CALL_COUNT = 5

        for i in range(CALL_COUNT):
            response = requests.get(httpserver.url_for("/200"))

        supergood_client.flush_cache()
        assert Api.post_events.call_args is not None
        args = Api.post_events.call_args[0][0]
        assert args[0]["request"] is not None
        assert args[0]["response"] is not None
        assert len(args) == CALL_COUNT
        supergood_client.kill()

    def test_captures_non_success_status_and_errors(
        self, httpserver: HTTPServer, supergood_client
    ):
        http_error_codes = [400, 401, 403, 404, 500, 501, 502, 503, 504]

        for code in http_error_codes:
            httpserver.expect_request(f"/{code}").respond_with_data(status=code)
            response = requests.get(httpserver.url_for(f"/{code}"))

        supergood_client.flush_cache()

        args = Api.post_events.call_args[0][0]
        assert len(args) == len(http_error_codes)

        responded_codes = set(map(lambda x: x["response"]["status"], args))
        assert responded_codes == set(http_error_codes)
        supergood_client.kill()

    def test_post_requests(self, httpserver: HTTPServer, supergood_client):
        httpserver.expect_request("/200", method="POST").respond_with_json(
            {"payload": "value"}
        )
        response = requests.post(httpserver.url_for("/200"))
        response.raise_for_status()
        json = response.json()
        supergood_client.flush_cache()

        assert json["payload"] == "value"
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        supergood_client.kill()

    def test_post_request_for_large_payload(
        self, httpserver: HTTPServer, supergood_client
    ):
        response = requests.post(COMPASS_URL, headers=HEADERS, json=PAYLOAD)
        response.raise_for_status()
        json = response.json()

        supergood_client.flush_cache()

        assert json.get("mapResults", {}).get("totalItems", 0) >= 0
        args = Api.post_events.call_args[0][0][0]
        assert args["request"] is not None
        assert args["response"] is not None
        supergood_client.kill()

    def test_hanging_response(self, httpserver: HTTPServer, supergood_client):
        HANG_TIME_IN_SECONDS = 2
        requests.get(f"{TEST_BED_URL}/200?sleep={HANG_TIME_IN_SECONDS}")
        supergood_client.flush_cache()

        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        supergood_client.kill()

    def test_posting_errors(self, supergood_client, session_mocker):
        _mock = session_mocker.patch(
            "supergood.api.Api.post_events", side_effect=Exception("Test Error")
        )
        _mock.start()

        requests.get(f"{TEST_BED_URL}/200")

        supergood_client.flush_cache()
        error_message = Api.post_errors.call_args[0][2]
        assert error_message == ERRORS["POSTING_EVENTS"]

        _mock.resetmock()
        session_mocker.patch("supergood.api.Api.post_events").start()
        supergood_client.kill()

    def test_different_http_library(self, httpserver: HTTPServer, supergood_client):
        http = urllib3.PoolManager()
        http.request("GET", f"{TEST_BED_URL}/200")

        supergood_client.flush_cache()

        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        supergood_client.kill()

    def test_aiohttp_library(self, httpserver: HTTPServer, supergood_client):
        async def aiohttp_get_request():
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{TEST_BED_URL}/200?success=true", headers=HEADERS, json=PAYLOAD
                ) as response:
                    return await response.json()

        async def aiohttp_post_request():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{TEST_BED_URL}/200?success=true", headers=HEADERS, json=PAYLOAD
                ) as response:
                    return await response.json()

        get_response = asyncio.run(aiohttp_get_request())
        post_response = asyncio.run(aiohttp_post_request())

        supergood_client.flush_cache()

        args = Api.post_events.call_args[0][0]
        assert len(args) == 2
        assert get_response["success"] == "true"
        assert post_response["success"] == "true"
        assert args[0]["response"] is not None
        assert args[0]["request"] is not None
        supergood_client.kill()
