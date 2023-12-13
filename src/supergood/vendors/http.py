import http.client
from uuid import uuid4

from ..constants import REQUEST_ID_KEY

HTTPS_PORT = http.client.HTTPS_PORT


def patch(cache_request, cache_response):
    _original_read = http.client.HTTPResponse.read
    _original_getresponse = http.client.HTTPConnection.getresponse
    _original_request = http.client.HTTPConnection.request
    _original_getheaders = http.client.HTTPResponse.getheaders

    def _wrap_read(httpResponse, amt=None):
        response_object = httpResponse
        response_body = _original_read(httpResponse, amt)
        request_id = getattr(response_object, REQUEST_ID_KEY)
        response_headers = _original_getheaders(httpResponse)
        response_status = response_object.status
        response_status_text = response_object.reason
        cache_response(
            request_id=request_id,
            response_body=response_body,
            response_headers=response_headers,
            response_status=response_status,
            response_status_text=response_status_text,
        )
        return response_body

    def _wrap_getresponse(httpConnection):
        response_object = _original_getresponse(httpConnection)
        try:
            request_id = getattr(httpConnection, REQUEST_ID_KEY)
            setattr(response_object, REQUEST_ID_KEY, request_id)
        except AttributeError:
            pass
        return response_object

    def _wrap_request(
        httpConnection,
        method,
        path,
        body=None,
        headers={},
        encode_chunked=False,
        **kwargs,
    ):
        request_id = str(uuid4())
        setattr(httpConnection, REQUEST_ID_KEY, request_id)
        scheme = "https" if httpConnection.port == HTTPS_PORT else "http"
        url = f"{scheme}://{httpConnection.host}{path}"
        cache_request(request_id, url, method, body, headers)
        return _original_request(
            httpConnection,
            method,
            path,
            body=body,
            headers=headers,
            encode_chunked=encode_chunked,
            **kwargs,
        )

    http.client.HTTPResponse.read = _wrap_read
    http.client.HTTPConnection.getresponse = _wrap_getresponse
    http.client.HTTPConnection.request = _wrap_request
