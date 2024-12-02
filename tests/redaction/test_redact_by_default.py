import pytest
import requests

from supergood.api import Api
from tests.helper import get_config, get_remote_config


@pytest.mark.parametrize(
    "supergood_client",
    [
        {
            "remote_config": get_remote_config(
                keys=[
                    ("responseBody.string", "ALLOW"),
                    ("responseBody.other_string", "REDACT"),
                    ("responseBody[].data[].string", "ALLOW"),
                ]
            ),
            "config": get_config(redact_by_default=True),
        }
    ],
    indirect=True,
)
class TestRedactByDefault:
    def test_redact_by_default(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "string": "abc",
                "other_string": "123",
            }
        )
        requests.get(httpserver.url_for("/200"))
        entries = supergood_client.flush_thread.append.call_args[0][0]
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args[0][0]
        response_body = args[0]["response"]["body"]
        metadata = args[0]["metadata"]
        assert response_body["string"] == "abc"  # not redacted!
        assert response_body["other_string"] == None  # redacted!
        assert len(metadata["sensitiveKeys"]) > 0
        # There are a bunch of request/response headers. Filter for just responseBody
        filtered = list(
            filter(
                lambda x: x["keyPath"].startswith("responseBody"),
                metadata["sensitiveKeys"],
            )
        )
        assert len(filtered) == 1
        assert filtered[0]["keyPath"] == "responseBody.other_string"
        assert filtered[0]["type"] == "string"
        assert filtered[0]["length"] == 3

    # Test that allowed keys with array indexers are not redacted
    def test_allowed_keys_of_arrays(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            [
                {
                    "data": [
                        {"string": "abc", "other_string": "sensitive"},
                        {"string": "abc", "other_string": "sensitive"},
                    ]
                }
            ]
        )
        requests.get(httpserver.url_for("/200"))
        entries = supergood_client.flush_thread.append.call_args[0][0]
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args[0][0]
        response_body = args[0]["response"]["body"]
        metadata = args[0]["metadata"]
        assert len(response_body) == 1
        assert len(response_body[0]["data"]) == 2
        assert response_body[0]["data"][0]["string"] == "abc"
        assert response_body[0]["data"][1]["string"] == "abc"

        assert response_body[0]["data"][0]["other_string"] == None
        assert response_body[0]["data"][1]["other_string"] == None

        assert len(metadata["sensitiveKeys"]) > 0
        # # There are a bunch of request/response headers. Filter for just responseBody
        filtered = list(
            filter(
                lambda x: x["keyPath"].startswith("responseBody"),
                metadata["sensitiveKeys"],
            )
        )
        assert len(filtered) == 2
        assert filtered[0]["keyPath"] == "responseBody[0].data[0].other_string"
        assert filtered[1]["keyPath"] == "responseBody[0].data[1].other_string"
        assert filtered[0]["type"] == "string" and filtered[1]["type"] == "string"
        assert filtered[0]["length"] == 9 and filtered[1]["length"] == 9
