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
                ]
            ),
            "config": get_config(force_redact_all=True),
        }
    ],
    indirect=True,
)
class TestRedactAll:
    def test_redact_all(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "string": "abc",
                "other_string": "123",
            }
        )
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        response_body = args[0]["response"]["body"]
        metadata = args[0]["metadata"]
        assert response_body["string"] == None  # redacted!
        assert response_body["other_string"] == None  # redacted!
        assert len(metadata["sensitiveKeys"]) > 0
        # There are a bunch of request/response headers. Filter for just responseBody
        filtered = list(
            filter(
                lambda x: x["keyPath"].startswith("responseBody"),
                metadata["sensitiveKeys"],
            )
        )
        assert len(filtered) == 2
        for entry in filtered:
            assert (
                entry["keyPath"] == "responseBody.string"
                or entry["keyPath"] == "responseBody.other_string"
            )
            assert entry["type"] == "string"
            assert entry["length"] == 3
