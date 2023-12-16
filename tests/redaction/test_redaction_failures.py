import pytest
import requests

from supergood.api import Api
from supergood.constants import ERRORS
from tests.helper import get_remote_config


@pytest.mark.parametrize(
    "broken_client",
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
    def test_redaction_fails(self, httpserver, broken_client):
        httpserver.expect_request("/200").respond_with_json({"string": "blah"})
        requests.get(httpserver.url_for("/200"))
        assert len(broken_client._response_cache) == 1  # event to flush
        broken_client.flush_cache()  # redaction fails! logs error but does not flush
        args = Api.post_events.call_args
        assert not args
        assert Api.post_errors.call_count == 1
        assert Api.post_errors.call_args[0][2] == ERRORS["REDACTION"]
