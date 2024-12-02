import pytest
import requests

from supergood.api import Api
from tests.helper import get_remote_config


@pytest.mark.parametrize(
    "supergood_client",
    [
        {
            "remote_config": get_remote_config(
                action="Ignore", location="requestHeaders", regex="scoobydoo"
            )
        }
    ],
    indirect=True,
)
class TestLocationRequestHeaders:
    def test_request_headers(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "string": "abc",
            }
        )
        requests.get(httpserver.url_for("/200"), headers={"X-test": "scoobydoo"})
        entries = supergood_client.flush_thread.append.call_args
        assert entries is None
        requests.get(httpserver.url_for("/200"), headers={"X-test": "scrappydootoo"})
        entries = supergood_client.flush_thread.append.call_args[0][0]
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
