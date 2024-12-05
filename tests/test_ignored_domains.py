import pytest
import requests

from supergood.api import Api
from tests.helper import get_config

TEST_BED_URL = "http://supergood-testbed.herokuapp.com"
EXTERNAL_URL = "https://api.ipify.org/?format=json"


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
    def test_ignores_requests_to_ignored_domains(self, supergood_client):
        requests.get(f"{TEST_BED_URL}/200")
        requests.get(f"{EXTERNAL_URL}")
        supergood_client.flush_cache()
        supergood_client.kill()
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        assert EXTERNAL_URL == args[0]["request"]["url"]
