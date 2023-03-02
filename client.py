#!/usr/bin/env python3

import http.client
from urllib.parse import urlparse
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse
from base64 import b64encode
import os
import signal
import sys

from dotenv import load_dotenv
from .logger import Logger
from .api import Api
from .constants import *
from .helpers import hash_values_from_keys, safe_parse_json

import threading

load_dotenv()

class Client(object):
    def __init__(self,
        client_id=os.getenv('SUPERGOOD_CLIENT_ID'),
        client_secret_id=os.getenv('SUPERGOOD_CLIENT_SECRET'),
        base_url=os.getenv('SUPERGOOD_BASE_URL')
    ):
        self.base_url = base_url
        self.client = http.client

        self.original_client = self.client
        self.original_request = self.client.HTTPConnection.request
        self.original_read = self.client.HTTPResponse.read
        self.original_getresponse = self.client.HTTPConnection.getresponse
        self.original_getheaders = self.client.HTTPResponse.getheaders

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
        self.api.set_event_sink_url(self.config['event_sink_endpoint'])
        self.api.set_error_sink_url(self.config['error_sink_endpoint'])

        self._intercept_getresponse()
        self._intercept_read()
        self._intercept_request()

        self._request_cache = {}
        self._response_cache = {}

        self.interval = self.set_interval(self.flush_cache, self.config['flush_interval'])

    def set_interval(self, func, sec):
        def func_wrapper():
            self.set_interval(func, sec)
            func()
        t = threading.Timer(sec, func_wrapper)
        t.start()
        return t

    def _restore_original_functions(self):
        self.client.HTTPConnection.request = self.original_request
        self.client.HTTPResponse.read = self.original_read
        self.client.HTTPConnection.getresponse = self.original_getresponse
        self.client.HTTPResponse.getheaders = self.original_getheaders

    def _intercept_request(self) -> None:
        """
        Logs original request
        Assigns a request ID to a request
        :return: None
        """
        def intercepted_request(_self, method, path, body=None, headers={}, encode_chunked=False, **kwargs) -> http.client.HTTPConnection.request:
                request_id = str(uuid4())
                setattr(_self, 'request_id', request_id)
                port = f':{_self.port}' if _self.port else ''
                scheme = 'https' if _self.port == self.original_client.HTTPS_PORT else 'http'
                full_url = f'{scheme}://{_self.host}{port}{path}'
                if (_self.host != self.base_url and _self.host not in self.config['ignored_domains']):
                    parsed_url = urlparse(full_url)
                    try:
                        request = {
                            'id': request_id,
                            'method': method,
                            'url': full_url,
                            'body': safe_parse_json(body),
                            'headers':  headers,
                            'path': path,
                            'search': parsed_url.query,
                            'requestedAt': datetime.now().isoformat()
                        }
                        self._request_cache[request_id] = request
                    except Exception as e:
                        self.log.error(
                            { 'request': request, 'config': self.config },
                            e,
                            ERRORS['CACHING_REQUEST']
                        )

                return self.original_request(_self, method, path, body=body, headers=headers, encode_chunked=encode_chunked, **kwargs)

        self.client.HTTPConnection.request = intercepted_request

    def _intercept_getresponse(self) -> None:
        """
        Tags a response with a request ID for matching
        when read event is called

        (No logging happens)
        :return: None
        """

        def intercepted_getresponse(_self):
            response = self.original_getresponse(_self)
            request_id = getattr(_self, 'request_id')
            setattr(response, 'request_id', request_id)
            return response

        self.client.HTTPConnection.getresponse = intercepted_getresponse

    def _intercept_read(self) -> None:
        """
        Logs original response
        :return: None
        """

        def intercepted_read(_self, *args):
            response_body = self.original_read(_self, *args)
            try:
                response_headers = self.original_getheaders(_self)
                request_id = getattr(_self, 'request_id')
                request = self._request_cache.get(request_id, None)
                body = response_body.decode('utf-8')

                if(request):
                    response = {
                            'body':  safe_parse_json(body),
                            'headers': dict(response_headers),
                            'status': _self.status,
                            'statusText': _self.reason,
                            'respondedAt': datetime.now().isoformat(),
                        }
                    self._response_cache[request_id] = hash_values_from_keys({
                        'request': request,
                        'response': response
                    }, self.config['keys_to_hash'])
                    self._request_cache.pop(request_id)
            except Exception as e:
                self.log.error(
                    { 'request': request, 'response': response, 'config': self.config },
                    e,
                    ERRORS['CACHING_RESPONSE']
                )

            return response_body

        self.client.HTTPResponse.read = intercepted_read

    def close(self) -> None:
        self.interval.cancel()
        self._restore_original_functions()
        self.flush_cache(force=True)

    def cleanup(self, sig, frame) -> None:
        if(sig):
            self.flush_cache(force=True)
            sys.exit(sig)

    def flush_cache(self, force=False) -> None:
        if(not self.config):
            self.log.info('Config not loaded yet, skipping flush')
            return

        response_keys = self._response_cache.keys()
        request_keys = self._request_cache.keys()

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
        except Exception as error:
            self.log.error({ 'data': data, 'config': self.config }, error, ERRORS['POSTING_EVENTS'])
        finally:
            self._response_cache.clear()
            if(force):
                self._request_cache.clear()
