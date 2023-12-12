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
                    ("responseBody.string", "REDACT"),
                    ("responseBody.number", "REDACT"),
                    ("responseBody.float", "REDACT"),
                    ("responseBody.bool", "REDACT"),
                    ("responseBody.complex_string", "REDACT"),
                    ("responseBody.array", "REDACT"),
                    ("responseBody.object", "REDACT"),
                ]
            ),
        }
    ],
    indirect=True,
)
class TestRedaction:
    def test_redact_one(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "string": "abc",
                "other_string": "Alex Klarfeld 911!",
            }
        )
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        response_body = args[0]["response"]["body"]
        metadata = args[0]["metadata"]
        assert response_body["string"] == None  # redacted!
        assert response_body["other_string"] == "Alex Klarfeld 911!"
        assert "responseBody.string" in metadata["sensitiveKeys"]
        assert metadata["sensitiveKeys"]["responseBody.string"] == "string:3"

    def test_each_redaction(self, httpserver, supergood_client):
        response_json = {
            "string": "abc",
            "number": 123,
            "float": 123.45,
            "bool": True,
            "complex_string": "Alex Klarfeld 911!",
            "array": ["a", "b", "c"],
            "object": {"param1": "value1", "param2": 2},
        }
        httpserver.expect_request("/200").respond_with_json(response_json)
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        body = args[0]["response"]["body"]
        for key in response_json:
            assert body[key] == None
        metadata = args[0]["metadata"]
        assert metadata and "sensitiveKeys" in metadata
        assert len(metadata["sensitiveKeys"]) == 7
        skeys = metadata["sensitiveKeys"]
        assert skeys["responseBody.string"] == "string:3"
        assert skeys["responseBody.number"] == "integer:3"
        assert skeys["responseBody.float"] == "float:6"  # string length
        assert skeys["responseBody.bool"] == "boolean:1"
        assert skeys["responseBody.complex_string"] == "string:18"
        assert skeys["responseBody.array"] == "array:3"
        assert skeys["responseBody.object"] == "object:193"
