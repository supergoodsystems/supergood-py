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
class TestLocationRequestHeaders:
    def test_request_headers(self, httpserver, supergood_client):
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
        supergood_client.flush_cache()
        assert Api.post_events.call_args is None
        requests.request(
            method="get", url=httpserver.url_for("/200"), data="blah scrappydootoo blah"
        )
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
