import http.client
from importlib.metadata import version
from uuid import uuid4

import urllib3
import urllib3.connection

from ..constants import REQUEST_ID_KEY

HTTPS_PORT = http.client.HTTPS_PORT


def patch(cache_request, cache_response):
    _original_read_chunked = urllib3.HTTPResponse.read_chunked
    _original_getheaders = http.client.HTTPResponse.getheaders
    _original_request = urllib3.connection.HTTPConnection.request

    def _wrap_read_chunked(urllib3HttpResponse, amt=None, decode_content=None):
        response_object = urllib3HttpResponse._original_response
        response_bytes = []

        for line in _original_read_chunked(urllib3HttpResponse, amt, decode_content):
            response_bytes.append(line)
            yield line

        request_id = getattr(response_object, REQUEST_ID_KEY)
        response_headers = _original_getheaders(response_object)
        response_body = b"".join(response_bytes)
        cache_response(
            request_id=request_id,
            response_body=response_body,
            response_headers=response_headers,
            response_status=response_object.status,
            response_status_text=response_object.reason,
        )

    def _wrap_request(http_connection, method, url, body=None, headers=None, **kwargs):
        request_id = str(uuid4())
        scheme = "https" if http_connection.port == HTTPS_PORT else "http"
        request_url = f"{scheme}://{http_connection.host}{url}"
        setattr(http_connection, REQUEST_ID_KEY, request_id)
        cache_request(request_id, request_url, method, body, headers)
        return _original_request(http_connection, method, url, body, headers, **kwargs)

    urllib3.HTTPResponse.read_chunked = _wrap_read_chunked
    if version("urllib3").startswith("2"):
        # This only needs to be patched in urllib3 v2+
        urllib3.connection.HTTPConnection.request = _wrap_request
