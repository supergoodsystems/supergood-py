import asyncio

import aiohttp
import requests
import urllib3
from dotenv import load_dotenv
from pytest_httpserver import HTTPServer

from supergood.api import Api
from supergood.constants import ERRORS
from tests.constants import *

load_dotenv()

TEST_BED_URL = "http://supergood-testbed.herokuapp.com"


class TestCore:
    def test_captures_all_outgoing_200_http_requests(
        self, httpserver: HTTPServer, supergood_client
    ):
        CALL_COUNT = 5

        for i in range(CALL_COUNT):
            response = requests.get(httpserver.url_for("/200"))

        assert supergood_client.flush_thread.append.call_args_list is not None
        assert len(supergood_client.flush_thread.append.call_args_list) == 5

    def test_captures_non_success_status_and_errors(
        self, httpserver: HTTPServer, supergood_client
    ):
        http_error_codes = [400, 401, 403, 404, 500, 501, 502, 503, 504]

        for code in http_error_codes:
            httpserver.expect_request(f"/{code}").respond_with_data(status=code)
            requests.get(httpserver.url_for(f"/{code}"))

        assert supergood_client.flush_thread.append.call_args_list is not None

        args = supergood_client.flush_thread.append.call_args_list
        assert len(args) == len(http_error_codes)

        responded_codes = set(
            map(lambda x: list(x[0][0].values())[0]["response"]["status"], args)
        )

        assert responded_codes == set(http_error_codes)

    def test_post_requests(self, httpserver: HTTPServer, supergood_client):
        httpserver.expect_request("/200", method="POST").respond_with_json(
            {"payload": "value"}
        )
        response = requests.post(httpserver.url_for("/200"))
        response.raise_for_status()
        json = response.json()

        assert json["payload"] == "value"
        args = supergood_client.flush_thread.append.call_args[0][0]
        assert len(args) == 1

    def test_post_request_for_large_payload(
        self, httpserver: HTTPServer, supergood_client
    ):
        response = requests.post(COMPASS_URL, headers=HEADERS, json=PAYLOAD)
        response.raise_for_status()
        json = response.json()

        assert json.get("mapResults", {}).get("totalItems", 0) >= 0
        args = supergood_client.flush_thread.append.call_args[0][0]
        assert list(args.values())[0]["request"] is not None
        assert list(args.values())[0]["request"] is not None

    def test_posting_errors(self, supergood_client, mocker):
        _mock = mocker.patch(
            "supergood.worker.Worker.append", side_effect=Exception("Test Error")
        )
        _mock.start()

        requests.get(f"{TEST_BED_URL}/200")

        error_message = Api.post_errors.call_args[0][2]
        assert error_message == ERRORS["CACHING_RESPONSE"]

    def test_different_http_library(self, httpserver: HTTPServer, supergood_client):
        http = urllib3.PoolManager()
        http.request("GET", f"{TEST_BED_URL}/200")

        args = supergood_client.flush_thread.append.call_args_list
        assert len(args) == 1

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

        args = supergood_client.flush_thread.append.call_args_list
        assert len(args) == 2
        assert get_response["success"] == "true"
        assert post_response["success"] == "true"
        first = list(args[0][0][0].values())[0]
        assert first["response"] is not None
        assert first["request"] is not None

    def test_tagging(self, httpserver: HTTPServer, supergood_client):
        tags = {"m": "mini", "w": "wumbo"}
        httpserver.expect_request("/tagging").respond_with_data(status=200)

        with supergood_client.tagging(tags):
            requests.get(httpserver.url_for("/tagging"))

        assert supergood_client.flush_thread.append.call_args is not None
        args = supergood_client.flush_thread.append.call_args[0][0]
        first = list(args.values())[0]
        assert first["request"] is not None
        assert first["response"] is not None
        assert first["metadata"] is not None
        assert first["metadata"]["tags"] == tags

    def test_layered_tagging(self, httpserver: HTTPServer, supergood_client):
        outer_tag = {"m": "mini"}
        inner_tag = {"w": "wumbo"}
        both_tags = {"m": "mini", "w": "wumbo"}
        httpserver.expect_request("/outer").respond_with_data(status=200)
        httpserver.expect_request("/inner").respond_with_data(status=200)
        httpserver.expect_request("/outeragain").respond_with_data(status=200)
        with supergood_client.tagging(outer_tag):
            requests.get(httpserver.url_for("/outer"))
            with supergood_client.tagging(inner_tag):
                requests.get(httpserver.url_for("/inner"))
            requests.get(httpserver.url_for("/outeragain"))

        assert supergood_client.flush_thread.append.call_args is not None
        call_list = supergood_client.flush_thread.append.call_args_list
        assert len(call_list) == 3
        # First call, tag shouldbe only the outer tag
        assert list(call_list[0][0][0].values())[0]["metadata"]["tags"] == outer_tag
        # Second call, should have both
        assert list(call_list[1][0][0].values())[0]["metadata"]["tags"] == both_tags
        # Third call, back to only outer
        assert list(call_list[2][0][0].values())[0]["metadata"]["tags"] == outer_tag
