import pytest
import requests

from supergood.api import Api
from supergood.client import Client
from tests.helper import get_config, get_remote_config


class TestNoRedaction:
    def test_ignore_redaction(self, httpserver, supergood_client):
        supergood_client.base_config["ignoreRedaction"] = True
        httpserver.expect_request("/200").respond_with_json(
            {
                "string": "abc",
                "complex_string": "Alex Klarfeld 911!",
            }
        )
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        response_body = args[0]["response"]["body"]
        assert response_body["string"] == "abc"  # not redacted!
        assert response_body["complex_string"] == "Alex Klarfeld 911!"
        assert "metadata" in args[0] and args[0]["metadata"] == {}

    def test_no_redaction(self, httpserver, supergood_client):
        httpserver.expect_request("/201").respond_with_json(
            {
                "string": "abc",
                "number": 123,
                "float": 123.45,
                "bool": True,
                "complex_string": "Alex Klarfeld 911!",
                "array": ["a", "b", "c"],
            }
        )
        requests.get(httpserver.url_for("/201"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        body = args[0]["response"]["body"]
        assert body["string"] == "abc"
        assert body["number"] == 123
        assert body["float"] == 123.45
        assert body["bool"] == True
        assert body["complex_string"] == "Alex Klarfeld 911!"
        assert "metadata" in args[0] and args[0]["metadata"] == {}
