import pytest
import requests
from pytest_httpserver import HTTPServer

from supergood.api import Api
from tests.helper import get_config

TEST_BED_URL = "http://supergood-testbed.herokuapp.com"


class TestDontLog:
    @pytest.mark.parametrize(
        "supergood_client",
        [
            {
                "config": get_config(
                    log_request_body=False,
                    log_request_headers=False,
                    log_response_body=False,
                    log_response_headers=False,
                ),
            }
        ],
        indirect=True,
    )
    def test_ignores_fields_when_set(self, httpserver: HTTPServer, supergood_client):
        httpserver.expect_request("/ignores").respond_with_data("super secret response")
        requests.post(httpserver.url_for("/ignores"), data={"mumbo": "jumbo"})

        args = supergood_client.flush_thread.append.call_args[0][0]

        assert len(args) == 1
        assert list(args.values())[0]["request"]["body"] == ""
        assert list(args.values())[0]["request"]["headers"] == {}
        assert list(args.values())[0]["response"]["body"] == ""
        assert list(args.values())[0]["response"]["headers"] == {}
