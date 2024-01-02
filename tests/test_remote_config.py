import re

import requests

from supergood.api import Api
from supergood.remote_config import parse_remote_config_json
from tests.helper import get_remote_config


class TestRemoteConfig:
    def test_remote_config_parse(self):
        remote_config = get_remote_config()
        parsed_config = parse_remote_config_json(remote_config)
        assert len(parsed_config) == 1
        assert parsed_config["vendor-id"] is not None
        assert len(parsed_config["vendor-id"].endpoints) == 1
        endpoint_config = parsed_config["vendor-id"].endpoints["endpoint-id"]
        assert endpoint_config.regex == re.compile("200")
        assert endpoint_config.location == "path"
        assert endpoint_config.action == "Allow"
        assert endpoint_config.sensitive_keys == []

    def test_client_ignores_before_config(self, httpserver, supergood_client):
        # Not a perfect way of simulating it but good enough
        supergood_client.remote_config = None  # config not pulled
        httpserver.expect_request("/200").respond_with_json({"key": "val"})
        requests.get(httpserver.url_for("/200"))
        assert supergood_client._request_cache == {}
        assert supergood_client._response_cache == {}
        supergood_client._get_config()  # Now there's a config
        httpserver.expect_request("/200").respond_with_json({"key": "val"})
        requests.get(httpserver.url_for("/200"))
        supergood_client.flush_cache()
        args = Api.post_events.call_args[0][0]
        assert len(args) == 1
        assert args[0]["response"]["body"] == {"key": "val"}
