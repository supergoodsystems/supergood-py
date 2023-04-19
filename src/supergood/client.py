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

from .vendors.requests import patch as patch_requests
from .vendors.urllib3 import patch as patch_urllib3
from .vendors.http import patch as patch_http
from .vendors.aiohttp import patch as patch_aiohttp

load_dotenv()

class Client(object):

    def __init__(self,
        client_id=os.getenv('SUPERGOOD_CLIENT_ID'),
        client_secret_id=os.getenv('SUPERGOOD_CLIENT_SECRET'),
        base_url=os.getenv('SUPERGOOD_BASE_URL'),
        config={}
    ):
        self.base_url = base_url if base_url else DEFAULT_SUPERGOOD_BASE_URL

        authorization = f'{client_id}:{client_secret_id}'

        header_options = {
                'Accept' : 'application/json, text/plain, */*',
                'Content-Type' : 'application/json',
                'Authorization' : 'Basic ' + b64encode(bytes(authorization, 'utf-8')).decode('utf-8')
            }
        self.config = DEFAULT_SUPERGOOD_CONFIG
        self.config.update(config)
        self.api = Api(header_options, base_url=self.base_url)
        self.log = Logger(self.__class__.__name__, self.config, self.api)

        self.api.set_logger(self.log)
        self.api.set_event_sink_url(self.config['eventSinkEndpoint'])
        self.api.set_error_sink_url(self.config['errorSinkEndpoint'])

        # Initialize patches here
        patch_requests(self._cache_request, self._cache_response)
        patch_urllib3(self._cache_request, self._cache_response)
        patch_http(self._cache_request, self._cache_response)
        patch_aiohttp(self._cache_request, self._cache_response)
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
        t.daemon = True
        t.start()
        return t

    def _cache_request(self, request_id, url, method, body, headers):
        host_domain = urlparse(url).hostname
        supergood_base_url = urlparse(self.base_url).hostname
        now = datetime.now().isoformat()

        # Don't log requests supergood is making to the event database
        if (host_domain != supergood_base_url and host_domain not in self.config['ignoredDomains']):
            parsed_url = urlparse(url)
            try:
                request = {
                    'request': {
                        'id': request_id,
                        'method': method,
                        'url': url,
                        'body': safe_parse_json(body),
                        'headers': dict(headers),
                        'path': parsed_url.path,
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

    def _cache_response(
        self,
        request_id,
        response_body,
        response_headers,
        response_status,
        response_status_text
    ) -> None:
        request, response = {}, {}
        try:
            request = self._request_cache.pop(request_id, None)
            decoded_body = safe_decode(response_body)
            if(request):
                response = {
                    'body': safe_parse_json(decoded_body),
                    'headers': dict(response_headers),
                    'status': response_status,
                    'statusText': response_status_text,
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
        self.flush_cache(force=True)

    def kill(self, *args) -> None:
        self.log.debug('Killing process, flushing cache forcefully.')
        self._request_cache.clear()
        self._response_cache.clear()
        self.interval.cancel()

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
