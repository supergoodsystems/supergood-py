import pytest
import requests

from supergood.api import Api
from supergood.constants import ERRORS
from tests.helper import get_remote_config


@pytest.mark.parametrize(
    "supergood_client",
    [
        {
            "remote_config": get_remote_config(
                keys=[
                    ("responseBody.string", "REDACT"),
                ]
            ),
        }
    ],
    indirect=True,
)
class TestRedactionFails:
    def test_redaction_fails(self, httpserver, supergood_client, mocker):
        httpserver.expect_request("/200").respond_with_json({"string": "blah"})
        requests.get(httpserver.url_for("/200"))
        mocker.patch("supergood.client.redact_values", side_effect=Exception).start()
        entries = supergood_client.flush_thread.append.call_args[0][0]
        assert len(entries) == 1  # there is something to be flushed!
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args
        assert not args  # but nothing got flushed, because redaction failed.
        # what did happen was an error post
        assert Api.post_errors.call_count == 1
        assert Api.post_errors.call_args[0][2] == ERRORS["REDACTION"]
