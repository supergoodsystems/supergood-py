import pytest
import requests

from supergood.api import Api
from tests.helper import get_remote_config


@pytest.mark.parametrize(
    "supergood_client",
    [
        {
            "remote_config": get_remote_config(
                keys=[
                    ("responseBody.array[]", "REDACT"),
                    ("responseBody.outerArray[].innerArray[]", "REDACT"),
                ]
            ),
        }
    ],
    indirect=True,
)
class TestRedactArrays:
    def test_redact_array_element(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "array": ["abc", "blah", ""],
            }
        )
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        body = args[0]["response"]["body"]
        metadata = args[0]["metadata"]
        assert body["array"] == [None, None, None]
        assert "sensitiveKeys" in metadata
        skeys = metadata["sensitiveKeys"]
        assert len(skeys) == 3
        assert skeys["responseBody.array[0]"] == "string:3"
        assert skeys["responseBody.array[1]"] == "string:4"
        assert skeys["responseBody.array[2]"] == "string:0"

    def test_redact_nested_array_element(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "outerArray": [
                    {"innerArray": ["wumbo"]},
                    {"innerArray": ["abc", ""]},
                ]
            }
        )
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        body = args[0]["response"]["body"]
        metadata = args[0]["metadata"]
        assert len(body["outerArray"]) == 2
        for i in range(2):
            assert "innerArray" in body["outerArray"][i]
            assert body["outerArray"][i]["innerArray"] == [None] * (i + 1)
        assert "sensitiveKeys" in metadata
        skeys = metadata["sensitiveKeys"]
        assert len(skeys) == 3
        assert skeys["responseBody.outerArray[0].innerArray[0]"] == "string:5"
        assert skeys["responseBody.outerArray[1].innerArray[0]"] == "string:3"
        assert skeys["responseBody.outerArray[1].innerArray[1]"] == "string:0"
