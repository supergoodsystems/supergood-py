from requests import Session


def patch(cache_request, cache_response):
    _original_send = Session.send

    # AK: The http.client.request method takes care of caching the request
    # requests.send just wraps http.client.request
    # TODO: See if this makes sense longer term to use, instead of http.client
    def _wrap_send(_self, request, **kwargs):
        return _original_send(_self, request, **kwargs)

    Session.send = _wrap_send
