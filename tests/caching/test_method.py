import pytest
import requests
from pytest_httpserver import HTTPServer

from supergood.api import Api
from tests.helper import get_remote_config


@pytest.mark.parametrize(
    "supergood_client",
    [{"remote_config": get_remote_config(action="Ignore", method="POST")}],
    indirect=True,
)
class TestMethod:
    def test_method_matching(self, httpserver: HTTPServer, supergood_client):
        httpserver.expect_request("/200", "POST").respond_with_json(
            {
                "string": "abc",
            }
        )
        httpserver.expect_request("/200", "GET").respond_with_json(
            {
                "string": "def",
            }
        )
        response1 = requests.request(
            method="post",
            url=httpserver.url_for("/200"),
        )
        # First call is ignored due to matching the ignored POST methods
        assert response1.json()["string"] == "abc"
        supergood_client.flush_cache()
        assert Api.post_events.call_args is None
        response2 = requests.request(method="get", url=httpserver.url_for("/200"))
        # Second call is cached and flushed because it does not match (i.e. is a new endpoint)
        assert response2.json()["string"] == "def"
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
