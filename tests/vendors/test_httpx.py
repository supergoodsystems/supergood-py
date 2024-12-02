import httpx
from pytest_httpserver import HTTPServer

from supergood.api import Api


class TestHttpx:
    def test_httpx_streaming(self, httpserver: HTTPServer, supergood_client):
        raw_response = 'data: {"valid": "json"}\n\ndata: [DONE]\n\n'
        httpserver.expect_request("/stream").respond_with_data(
            response_data=raw_response
        )
        resp = b""
        with httpx.stream("GET", httpserver.url_for("/stream")) as s:
            for data in s.iter_bytes(chunk_size=1):
                resp += data
        assert resp.decode("utf-8") == raw_response
        entries = supergood_client.flush_thread.append.call_args[0][0]
        supergood_client.flush_cache(entries)
        args = Api.post_events.call_args[0][0]
        # verify 2 entries, one each for each response field
        assert len(args[0]["response"]["body"]) == 2
        # verifies valid JSON is indexible
        assert args[0]["response"]["body"][0]["data"][0]["valid"] == "json"
