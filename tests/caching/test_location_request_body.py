import pytest
import requests

from supergood.api import Api
from tests.helper import get_remote_config


@pytest.mark.parametrize(
    "supergood_client",
    [
        {
            "remote_config": get_remote_config(
                action="Ignore", location="requestBody", regex="scoobydoo"
            )
        }
    ],
    indirect=True,
)
class TestLocationRequestBody:
    def test_request_body(self, httpserver, supergood_client):
        httpserver.expect_request("/200").respond_with_json(
            {
                "string": "abc",
            }
        )
        requests.request(
            method="get",
            url=httpserver.url_for("/200"),
            data="blah scoobydoobydoo blah",
        )
        # verify that the event was not appended to the worker
        entries = supergood_client.flush_thread.append.call_args
        assert entries is None
        assert Api.post_events.call_args is None
        requests.request(
            method="get", url=httpserver.url_for("/200"), data="blah scrappydootoo blah"
        )
        # in this case the event _was_ added to the worker
        entries = supergood_client.flush_thread.append.call_args[0][0]
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
