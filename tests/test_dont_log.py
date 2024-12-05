import pytest
import requests

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
    def test_ignores_fields_when_set(self, supergood_client):
        requests.get(f"{TEST_BED_URL}/200")
        supergood_client.flush_cache()
        supergood_client.kill()
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        assert args[0]["request"]["body"] == ""
        assert args[0]["request"]["headers"] == {}
        assert args[0]["response"]["body"] == ""
        assert args[0]["response"]["headers"] == {}
