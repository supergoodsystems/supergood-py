#!/usr/bin/env python3

import http.client
import copy
from requests import post
from urllib.parse import urlparse
from typing import Union
from logging import getLogger, basicConfig, INFO
basicConfig(level=INFO)


class Interceptor:
    """
    This class provides simple functions and methods
    to patch some parts of the standard Python3 HTTP library,
    such as http.client (maybe something else in future)

    Work In Progress, PoC stage.

    Can be used to catch API calls from other libraries, intercept it,
    sniff and something else.

    This is the base class, so it is no need to use it directly.
    Please, use the 'Interceptor' class instance or write your own
    required handlers in the 'Interceptor'.

    Thanks.

    To read more:
    1. https://docs.python.org/3/library/http.client.html
    2. https://github.com/python/cpython/tree/3.8/Lib/http/client.py
    """

    def __init__(self, client_id, client_secret_id, base_url):
        """
        Initialize Interceptor base class.
        Not really required IRL, but helpful for purposes
        like saving of the original 'send' point + client settings
        :param client: client to use to, 'http.client' as default one
        """
        self.client = http.client
        self.original_request = self.client.HTTPConnection.request
        self.original_getresponse = self.client.HTTPConnection.getresponse
        self.original_send = self.client.HTTPConnection.send
        self.log = getLogger(self.__class__.__name__)

        self._dump_response()
        self._dump_send()

    def _restore_request(self) -> None:
        """
        Restore original request function call after use
        :return: None
        """
        self.client.HTTPConnection.request = self.original_request

    def _restore_getresponse(self) -> None:
        """
        Restore original getresponse function call after use
        :return: None
        """
        self.client.HTTPConnection.getresponse = self.original_getresponse

    def _dump_send(self) -> None:
        """
        Logs original send
        :return: None
        """
        original_send = self.client.HTTPConnection.send

        def patch(_self, data, *args, **kwargs) -> http.client.HTTPConnection.send:
            self.log.info(msg=f"Send:\r\n{data}")
            return original_send(_self, data)

        self.client.HTTPConnection.send = patch

    def _dump_request(self) -> None:
        """
        Logs original request
        :return: None
        """
        original_request = self.client.HTTPConnection.request

        def patch(_self, method, url, body=None, headers={}, encode_chunked=False, **kwargs) -> http.client.HTTPConnection.request:
            self.log.info(msg=f"Request: {url} {method} {body} {headers} {kwargs}")
            return original_request(_self, method, url, body=body, headers=headers, encode_chunked=encode_chunked, **kwargs)

        self.client.HTTPConnection.request = patch

    # TODO: This is not working, need to fix
    def _dump_response(self) -> None:
        """
        Logs original response
        :return: None
        """
        original_getresponse = self.client.HTTPConnection.getresponse

        def patch(_self, *args, **kwargs) -> http.client.HTTPResponse:
            original_response_object = original_getresponse(_self, *args, **kwargs)

            def intercepted_read(_s, *args):
                response_body = original_response_object.read(_s, *args)
                self.log.info(msg=f"Response: {response_body}")
                return response
            func_type = type(original_response_object.read)
            print(original_response_object.read)

            original_response_object.read = func_type(intercepted_read, original_response_object)
            print(original_response_object.read)

            return original_response_object

        self.client.HTTPConnection.getresponse = patch

# class Interceptor(InterceptorBase):
#     def __init__(self, client: http.client or None = None):
#         """
#         Wrap 'InterceptorBase' as decorator or handler functions
#         :param client: client to use
#         """
#         super().__init__(client=client)

#     def target(self, host, port) -> callable:
#         """
#         Wrap function to lead requests to another target
#         :param host: host to lead to
#         :param port: port to lead to
#         :return: wrap function
#         """

#         def wrap(function):
#             def wrapped_function(*args, **kwargs):
#                 self._patch_target(patch_host=host, patch_port=port)
#                 function_output = function(*args, **kwargs)
#                 self._restore_send()
#                 return function_output

#             return wrapped_function

#         return wrap

#     def data(self, data: Union[str, bytes]) -> callable:
#         """
#         Replace original data with something new
#         :param data: new data
#         :return: wrap function
#         """

#         def wrap(function):
#             def wrapped_function(*args, **kwargs):
#                 self._patch_data(patch_data_body=data)
#                 function_output = function(*args, **kwargs)
#                 self._restore_send()
#                 return function_output

#             return wrapped_function

#         return wrap

#     def dump(self) -> callable:
#         """
#         Dumps original request
#         :return: wrap function
#         """
#         def wrap(function):
#             def wrapped_function(*args, **kwargs):
#                 self._dump_request()
#                 function_output = function(*args, **kwargs)
#                 self._restore_send()
#                 return function_output

#             return wrapped_function

#         return wrap

#     def sniff(self, listener: str) -> callable:
#         """
#         Sniff requests
#         :param listener: listener endpoint
#         :return: wrap function
#         """

#         def wrap(function):
#             def wrapped_function(*args, **kwargs):
#                 self._sniff_request(listener_url=listener)
#                 function_output = function(*args, **kwargs)
#                 self._restore_send()
#                 return function_output

#             return wrapped_function

#         return wrap
