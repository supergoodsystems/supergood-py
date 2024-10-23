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
                    ("requestBody", "REDACT"),
                    ("responseBody", "REDACT"),
                    ("requestHeaders", "REDACT"),
                    ("responseHeaders", "REDACT"),
                ]
            ),
        }
    ],
    indirect=True,
)
class TestTopLevelRedaction:
    def test_top_level_redactions(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json({"string": "abc"})
        requests.get(httpserver.url_for("/200"))
        entries = supergood_client.flush_thread.append.call_args[0][0]
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        assert args[0]["request"]["body"] == None
        assert args[0]["request"]["headers"] == None
        assert args[0]["response"]["body"] == None
        assert args[0]["response"]["headers"] == None
