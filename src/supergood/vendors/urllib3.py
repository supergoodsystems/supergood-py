import http

import urllib3

from ..constants import REQUEST_ID_KEY


def patch(cache_request, cache_response):
    _original_read_chunked = urllib3.HTTPResponse.read_chunked
    _original_getheaders = http.client.HTTPResponse.getheaders

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

    urllib3.HTTPResponse.read_chunked = _wrap_read_chunked
