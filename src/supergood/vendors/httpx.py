import json
from typing import Optional
from uuid import uuid4

import httpx

from ..constants import REQUEST_ID_KEY
from .helpers import DataclassesJSONEncoder, ServerSentEvent


def patch(cache_request, cache_response):
    _original_handle_request = httpx.HTTPTransport.handle_request
    _original_response_read = httpx.Response.read
    _original_response_iter_lines = httpx.Response.iter_lines
    _original_response_iter_bytes = httpx.Response.iter_bytes

    _original_handle_async_request = httpx.AsyncHTTPTransport.handle_async_request
    _original_response_aread = httpx.Response.aread
    _original_response_aiter_bytes = httpx.Response.aiter_bytes
    _original_response_aiter_lines = httpx.Response.aiter_lines

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

    def _wrap_iter_lines(response: httpx.Response):
        request_id = getattr(response, REQUEST_ID_KEY)
        status_text = response.extensions.get("reason_phrase", None)
        if status_text:
            status_text = status_text.decode("utf-8")
        response_parts = []
        for line in _original_response_iter_lines(response):
            if line:
                response_parts.append(line)
            yield line
        response_body = "\n".join(response_parts)
        cache_response(
            request_id,
            response_body,
            response.headers,
            response.status_code,
            status_text,
        )

    async def _wrap_aiter_lines(response: httpx.Response):
        request_id = getattr(response, REQUEST_ID_KEY)
        status_text = response.extensions.get("reason_phrase", None)
        if status_text:
            status_text = status_text.decode("utf-8")
        response_parts = []
        async for line in _original_response_aiter_lines(response):
            if line:
                response_parts.append(line)
            yield line
        response_body = "\n".join(response_parts)
        cache_response(
            request_id,
            response_body,
            response.headers,
            response.status_code,
            status_text,
        )

    def _parse_sse(chunk: str):
        data = []
        event = None
        id = None
        retry = None

        for line in chunk.splitlines():
            if not line:
                # empty newline = dispatch
                sse = ServerSentEvent(event, data, id, retry)
                return sse
            if line.startswith(":"):
                return None
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                event = value
            elif field == "data":
                # parse the value as json if it's serializable. otherwise use a string
                try:
                    serialized = json.loads(value)
                except:
                    serialized = value
                data.append(serialized)
            elif field == "id":
                if "\0" not in value:
                    id = value
            elif field == "retry":
                try:
                    retry = int(value)
                except (TypeError, ValueError):
                    # what do?
                    pass
        # if we got to the end but didn't get a dispatch instruction, sse was invalid
        return None

    def _wrap_iter_bytes(response: httpx.Response, chunk_size: Optional[int] = None):
        request_id = getattr(response, REQUEST_ID_KEY)
        status_text = response.extensions.get("reason_phrase", None)
        if status_text:
            status_text = status_text.decode("utf-8")
        response_chunks = []
        data = b""
        for chunk in _original_response_iter_bytes(response, chunk_size):
            for line in chunk.splitlines(keepends=True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    # assume it's an SSE response
                    decoded = data.decode("utf-8")
                    try:
                        sse = _parse_sse(decoded)
                        if sse:
                            response_chunks.append(sse)
                    except Exception:
                        # failing SSE parsing, just return as string
                        response_chunks.append(decoded)
                    data = b""
            yield chunk
        if len(data):
            # must have been an invalid chunk, append it anyway
            response_chunks.append(data)
        try:
            response_body = json.dumps(response_chunks, cls=DataclassesJSONEncoder)
        except Exception:
            response_body = str(response_chunks)
        cache_response(
            request_id,
            response_body,
            response.headers,
            response.status_code,
            status_text,
        )

    async def _wrap_aiter_bytes(
        response: httpx.Response, chunk_size: Optional[int] = None
    ):
        request_id = getattr(response, REQUEST_ID_KEY)
        status_text = response.extensions.get("reason_phrase", None)
        if status_text:
            status_text = status_text.decode("utf-8")
        response_chunks = []
        data = b""
        async for chunk in _original_response_aiter_bytes(response, chunk_size):
            for line in chunk.splitlines(keepends=True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    # assume it's an SSE response
                    decoded = data.decode("utf-8")
                    try:
                        sse = _parse_sse(decoded)
                        if sse:
                            response_chunks.append(sse)
                    except Exception:
                        # failing SSE parsing, just return as string
                        response_chunks.append(decoded)
                    data = b""
            yield chunk
        if len(data):
            # must have been an invalid chunk, append it anyway
            response_chunks.append(data)
        try:
            response_body = json.dumps(response_chunks, cls=DataclassesJSONEncoder)
        except Exception:
            response_body = str(response_chunks)
        cache_response(
            request_id,
            response_body,
            response.headers,
            response.status_code,
            status_text,
        )

    httpx.HTTPTransport.handle_request = _wrap_handle_request
    httpx.Response.read = _wrap_response_read
    httpx.Response.iter_lines = _wrap_iter_lines
    httpx.Response.iter_bytes = _wrap_iter_bytes

    httpx.AsyncHTTPTransport.handle_async_request = _wrap_handle_async_request
    httpx.Response.aread = _wrap_response_aread
    httpx.Response.aiter_lines = _wrap_aiter_lines
    httpx.Response.aiter_bytes = _wrap_aiter_bytes
