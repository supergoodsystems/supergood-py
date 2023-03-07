#!/usr/bin/env python3

import http.client
import urllib3
import signal
import os
import sys
import traceback
import jsonpickle
import json
import atexit
import threading

from urllib.parse import urlparse
from uuid import uuid4
from datetime import datetime
from base64 import b64encode
from dotenv import load_dotenv
from .logger import Logger
from .api import Api
from .constants import *
from .helpers import hash_values_from_keys, safe_parse_json, safe_decode

load_dotenv()

class Client(object):

    def __init__(self,
        client_id=os.getenv('SUPERGOOD_CLIENT_ID'),
        client_secret_id=os.getenv('SUPERGOOD_CLIENT_SECRET'),
        base_url=os.getenv('SUPERGOOD_BASE_URL')
    ):
        self.base_url = base_url if base_url else DEFAULT_SUPERGOOD_BASE_URL
        self.http_client = http.client

        self.urllib3_HTTPResponse = urllib3.HTTPResponse
        self.original_read_chunked = self.urllib3_HTTPResponse.read_chunked

        self.original_http_client = self.http_client
        self.original_http_client_request = self.http_client.HTTPConnection.request
        self.original_http_client_read = self.http_client.HTTPResponse.read
        self.original_http_client_getresponse = self.http_client.HTTPConnection.getresponse
        self.original_http_client_getheaders = self.http_client.HTTPResponse.getheaders

        authorization = f'{client_id}:{client_secret_id}'
        header_options = {
                'Accept' : 'application/json, text/plain, */*',
                'Content-Type' : 'application/json',
                'Authorization' : 'Basic ' + b64encode(bytes(authorization, 'utf-8')).decode('utf-8')
            }

        self.api = Api(header_options, base_url=self.base_url)
        self.config = self.api.fetch_config()
        self.log = Logger(self.__class__.__name__, self.config, self.api)

        self.api.set_logger(self.log)
        self.api.set_event_sink_url(self.config['eventSinkEndpoint'])
        self.api.set_error_sink_url(self.config['errorSinkEndpoint'])

        self._intercept_getresponse()
        self._intercept_read()
        self._intercept_request()
        self._intercept_read_chunked()

        self._request_cache = {}
        self._response_cache = {}

        self.interval = self.set_interval(self.flush_cache, self.config['flushInterval'] / 1000)

        # On clean exit, or terminated exit - exit gracefully
        atexit.register(self.close)

    def set_interval(self, func, sec):
        def func_wrapper():
            self.set_interval(func, sec)
            func()
        t = threading.Timer(sec, func_wrapper)

        # Function will exit and end when script ends
        t.setDaemon(True)
        t.start()
        return t

    def _restore_original_functions(self):
        self.http_client.HTTPConnection.request = self.original_http_client_request
        self.http_client.HTTPResponse.read = self.original_http_client_read
        self.http_client.HTTPConnection.getresponse = self.original_http_client_getresponse
        self.http_client.HTTPResponse.getheaders = self.original_http_client_getheaders

    def _intercept_request(self) -> None:
        """
        Intercepts the requests made by http.client.HTTPConnection.request
        and logs them in memory to be paired up later with a response
        :return: None
        """
        def intercepted_request(_self, method, path, body=None, headers={}, encode_chunked=False, **kwargs) -> http.client.HTTPConnection.request:
            self._cache_request(_self, method, path, body, headers)
            return self.original_http_client_request(_self, method, path, body=body, headers=headers, encode_chunked=encode_chunked, **kwargs)

        self.http_client.HTTPConnection.request = intercepted_request

    def _intercept_getresponse(self) -> None:
        """
        Tags a response object with a request ID for matching
        when read or read_chunked methods are called

        The request ID is used to fetch the associated request
        from the cache and log it along with the response
        :return: None
        """

        def intercepted_getresponse(_self):
            response = self.original_http_client_getresponse(_self)
            request_id = getattr(_self, REQUEST_ID_KEY)
            setattr(response, REQUEST_ID_KEY, request_id)
            return response

        self.http_client.HTTPConnection.getresponse = intercepted_getresponse

    def _intercept_read_chunked(self) -> None:
        """
        Intercepts the read_chunked function of the urllib3.HTTPResponse object
        Note: This method does NOT exist on http.client.HTTPResponse
        and is used for streaming responses of large sized requests
        :return: None
        """
        def intercepted_read_chunked(_self, amt=None, decode_content=None):
            response_object = _self._original_response
            response_bytes = []
            for line in self.original_read_chunked(_self, amt, decode_content):
                response_bytes.append(line)
                yield line

            response_body = b''.join(response_bytes)
            self._cache_response(response_object, response_body)

        self.urllib3_HTTPResponse.read_chunked = intercepted_read_chunked

    def _intercept_read(self) -> None:
        """
        Intercepts the read function of the http.client.HTTPResponse object
        this method DOES exist on http.client.HTTPResponse
        and is used for non-streaming responses of small sized requests
        :return: None
        """

        def intercepted_read(_self, amt=None):
            response_object = _self
            response_body = self.original_http_client_read(response_object, amt)
            self._cache_response(response_object, response_body)
            return response_body

        self.http_client.HTTPResponse.read = intercepted_read

    def _cache_request(self, connection_object, method, path, body, headers):
        request_id = str(uuid4())
        setattr(connection_object, REQUEST_ID_KEY, request_id)
        scheme = 'https' if connection_object.port == self.original_http_client.HTTPS_PORT else 'http'
        full_url = f'{scheme}://{connection_object.host}{path}'
        host_domain = urlparse(full_url).hostname
        supergood_base_url = urlparse(self.base_url).hostname
        now = datetime.now().isoformat()

        # Don't log requests supergood is making to the event database
        if (host_domain != supergood_base_url and host_domain not in self.config['ignoredDomains']):
            parsed_url = urlparse(full_url)
            try:
                request = {
                    'request': {
                        'id': request_id,
                        'method': method,
                        'url': full_url,
                        'body': safe_parse_json(body),
                        'headers': dict(headers),
                        'path': path,
                        'search': parsed_url.query,
                        'requestedAt': now,
                    }
                }
                self._request_cache[request_id] = request
            except Exception as e:
                exc_info = sys.exc_info()
                error_string = ''.join(traceback.format_exception(*exc_info))
                self.log.error(
                    {
                        'request': jsonpickle.encode(request, unpicklable=False),
                        'config': jsonpickle.encode(self.config , unpicklable=False)
                    },
                    error_string,
                    ERRORS['CACHING_REQUEST']
                )



    def _cache_response(self, response_object, response_body) -> None:
        request, response = {}, {}
        try:
            response_headers = self.original_http_client_getheaders(response_object)
            request_id = getattr(response_object, REQUEST_ID_KEY)
            request = self._request_cache.pop(request_id, None)
            decoded_body = safe_decode(response_body)
            if(request):
                response = {
                    'body': safe_parse_json(decoded_body),
                    'headers': dict(response_headers),
                    'status': response_object.status,
                    'statusText': response_object.reason,
                    'respondedAt': datetime.now().isoformat(),
                }
                self._response_cache[request_id] = hash_values_from_keys({
                    'request': request['request'],
                    'response': response
                }, self.config['keysToHash'])
        except Exception as e:
            exc_info = sys.exc_info()
            error_string = ''.join(traceback.format_exception(*exc_info))
            self.log.error(
                {
                    'request': jsonpickle.encode(request, unpicklable=False),
                    'response': jsonpickle.encode(response, unpicklable=False),
                    'config': jsonpickle.encode(self.config , unpicklable=False)
                },
                error_string,
                ERRORS['CACHING_RESPONSE']
            )

    def close(self, *args) -> None:
        self.log.debug('Cleaning up, flushing cache gracefully.')
        self.interval.cancel()
        self._restore_original_functions()
        self.flush_cache(force=True)

    def flush_cache(self, force=False) -> None:
        if(not self.config):
            self.log.info('Config not loaded yet, skipping flush')
            return

        response_keys = list(self._response_cache.keys())
        request_keys = list(self._request_cache.keys())
        # If there are no responses in cache, just exit
        if(len(response_keys) == 0 and not force):
            return

        # If we're forcing a flush but there's nothing in the cache, exit here
        if(force and len(response_keys) == 0 and len(request_keys) == 0):
            return

        data = list(self._response_cache.values())

        if(force):
            data += list(self._request_cache.values())
        try:
            self.log.debug(f'Flushing {len(data)} items')
            self.api.post_events(data)
        except Exception as e:
            exc_info = sys.exc_info()
            error_string = ''.join(traceback.format_exception(*exc_info))
            self.log.error(
                {
                    'data': jsonpickle.encode(data, unpicklable=False),
                    'config': jsonpickle.encode(self.config, unpicklable=False),
                }, error_string, ERRORS['POSTING_EVENTS'])
        finally:
            for response_key in response_keys:
                self._response_cache.pop(response_key, None)
            if(force):
                for request_key in request_keys:
                    self._request_cache.pop(request_key, None)
