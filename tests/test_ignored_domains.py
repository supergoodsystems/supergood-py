import pytest
import requests
from pytest_httpserver import HTTPServer

from supergood.api import Api
from tests.helper import get_config

TEST_BED_URL = "http://supergood-testbed.herokuapp.com"


class TestIgnoreDomain:
    @pytest.mark.parametrize(
        "supergood_client",
        [
            {
                "config": get_config(
                    ignored_domains=["supergood-testbed.herokuapp.com"]
                ),
            }
        ],
        indirect=True,
    )
    def test_ignores_requests_to_ignored_domains(
        self, httpserver: HTTPServer, supergood_client
    ):
        requests.get(f"{TEST_BED_URL}/200")
        args = supergood_client.flush_thread.append.call_args_list
        assert len(args) == 0
        httpserver.expect_request("/ignore-domain").respond_with_data("wumbo")
        requests.get(httpserver.url_for("/ignore-domain"))
        args = supergood_client.flush_thread.append.call_args_list
        assert len(args) == 1
        list(args[0][0][0].values())[0]
        # double check that it's the expected domain
        assert (
            "http://localhost/ignore-domain"
            == list(args[0][0][0].values())[0]["request"]["url"]
        )
