from uuid import uuid4

import httpx

from ..constants import REQUEST_ID_KEY


def patch(cache_request, cache_response):
    _original_handle_request = httpx.HTTPTransport.handle_request
    _original_response_read = httpx.Response.read

    _original_handle_async_request = httpx.AsyncHTTPTransport.handle_async_request
    _original_response_aread = httpx.Response.aread

    def _wrap_handle_request(
        httpTransport: httpx.HTTPTransport, request: httpx.Request
    ):
        request_id = str(uuid4())
        cache_request(
            request_id,
            str(request.url),
            request.method,
            b"".join(request.stream).decode("utf-8"),
            request.headers,
        )
        response = _original_handle_request(httpTransport, request)
        setattr(response, REQUEST_ID_KEY, request_id)
        return response

    async def _wrap_handle_async_request(
        http_transport: httpx.AsyncHTTPTransport, request: httpx.Request
    ) -> httpx.Response:
        request_id = str(uuid4())
        cache_request(
            request_id,
            str(request.url),
            request.method,
            b"".join(request.stream).decode("utf-8"),
            request.headers,
        )
        response = await _original_handle_async_request(http_transport, request)
        setattr(response, REQUEST_ID_KEY, request_id)
        return response

    def _wrap_response_read(response: httpx.Response):
        response_body = _original_response_read(response)
        request_id = getattr(response, REQUEST_ID_KEY)
        status_text = response.extensions.get("reason_phrase", None)
        if status_text:
            status_text = status_text.decode("utf-8")
        cache_response(
            request_id,
            response.text,
            response.headers,
            response.status_code,
            status_text,
        )
        return response_body

    async def _wrap_response_aread(response: httpx.Response):
        response_body = await _original_response_aread(response)
        request_id = getattr(response, REQUEST_ID_KEY)
        status_text = response.extensions.get("reason_phrase", None)
        if status_text:
            status_text = status_text.decode("utf-8")
        cache_response(
            request_id,
            response.text,
            response.headers,
            response.status_code,
            status_text,
        )
        return response_body

    httpx.HTTPTransport.handle_request = _wrap_handle_request
    httpx.Response.read = _wrap_response_read

    httpx.AsyncHTTPTransport.handle_async_request = _wrap_handle_async_request
    httpx.Response.aread = _wrap_response_aread
