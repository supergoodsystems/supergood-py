from uuid import uuid4

import aiohttp

from ..constants import REQUEST_ID_KEY


def patch(cache_request, cache_response):
    _original_request = aiohttp.client.ClientSession._request
    _original_read = aiohttp.client_reqrep.ClientResponse.read

    async def _wrap_request(clientSession, method, url, *args, **kwargs):
        request_id = str(uuid4())
        body = kwargs.get("json", None) or kwargs.get("data", None)
        headers = kwargs.get("headers", None)

        cache_request(request_id, url, method, body, headers)

        response = await _original_request(clientSession, method, url, *args, **kwargs)
        setattr(response, REQUEST_ID_KEY, request_id)

        return response

    async def _wrap_read(clientResponse):
        request_id = getattr(clientResponse, REQUEST_ID_KEY)
        response_headers = clientResponse.headers
        response_status = clientResponse.status
        response_status_text = clientResponse.reason
        response_body = await _original_read(clientResponse)

        cache_response(
            request_id,
            response_body,
            response_headers,
            response_status,
            response_status_text,
        )
        return response_body

    aiohttp.client.ClientSession._request = _wrap_request
    aiohttp.client_reqrep.ClientResponse.read = _wrap_read
