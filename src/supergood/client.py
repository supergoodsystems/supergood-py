#!/usr/bin/env python3

import atexit
import os
import sys
import traceback
from base64 import b64encode
from datetime import datetime
from importlib.metadata import version
from urllib.parse import urlparse

import jsonpickle
from dotenv import load_dotenv
from tldextract import extract

from .api import Api
from .constants import *
from .helpers import redact_values, safe_decode, safe_parse_json
from .logger import Logger
from .remote_config import parse_remote_config_json
from .repeating_thread import RepeatingThread
from .vendors.aiohttp import patch as patch_aiohttp
from .vendors.http import patch as patch_http
from .vendors.requests import patch as patch_requests
from .vendors.urllib3 import patch as patch_urllib3

load_dotenv()


class Client(object):
    def __init__(
        self,
        client_id=os.getenv("SUPERGOOD_CLIENT_ID"),
        client_secret_id=os.getenv("SUPERGOOD_CLIENT_SECRET"),
        base_url=os.getenv("SUPERGOOD_BASE_URL"),
        config={},
    ):
        self.base_url = base_url if base_url else DEFAULT_SUPERGOOD_BASE_URL

        authorization = f"{client_id}:{client_secret_id}"

        header_options = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Authorization": "Basic "
            + b64encode(bytes(authorization, "utf-8")).decode("utf-8"),
            "supergood-api": "supergood-py",
            "supergood-api-version": version("supergood"),
        }
        self.base_config = DEFAULT_SUPERGOOD_CONFIG
        self.base_config.update(config)

        self.remote_config = None
        self.remote_config_thread = RepeatingThread(
            self.get_config, self.base_config["configInterval"] / 1000
        )

        self.api = Api(header_options, self.base_url)
        self.log = Logger(self.__class__.__name__, self.base_config, self.api)

        self.api.set_logger(self.log)
        self.api.set_event_sink_url(self.base_config["eventSinkEndpoint"])
        self.api.set_error_sink_url(self.base_config["errorSinkEndpoint"])
        self.api.set_config_pull_url(self.base_config["configPullEndpoint"])

        self._request_cache = {}
        self._response_cache = {}

        # Initialize patches here
        patch_requests(self._cache_request, self._cache_response)
        patch_urllib3(self._cache_request, self._cache_response)
        patch_http(self._cache_request, self._cache_response)
        patch_aiohttp(self._cache_request, self._cache_response)

        self.flush_thread = RepeatingThread(
            self.flush_cache, self.base_config["flushInterval"] / 1000
        )

        # On clean exit, or terminated exit - exit gracefully
        atexit.register(self.close)

    def _get_test_val(
        self,
        location,
        url=None,
        request_body=None,
        request_headers=None,
    ):
        match location:
            case "path":
                return urlparse(url).path
            case "url":
                return url
            case "domain":
                return extract(url).domain
            case "subdomain":
                return extract(url).subdomain
            case "request_headers":
                return str(request_headers)
            case "request_body":
                to_search = str(request_body)

    def _should_ignore(
        self,
        host_domain,
        url=None,
        request_body=None,
        request_headers=None,
        response_body=None,
        response_headers=None,
    ):
        supergood_base_url = urlparse(self.base_url).hostname
        # If we haven't fetched the remote config yet, always ignore
        if (
            not self.remote_config
            or host_domain == supergood_base_url
            or host_domain in self.base_config["ignoredDomains"]
        ):
            return True
        for vendor_domain in self.remote_config:
            if vendor_domain in host_domain:
                # Matched vendor, check for endpoint match
                for endpoint in self.remote_config[vendor_domain].endpoints:
                    test = _get_test_val(endpoint.location, url=url)

    def _cache_request(self, request_id, url, method, body, headers):
        host_domain = urlparse(url).hostname

        # Check that we should cache the request
        if self._should_ignore(
            host_domain, url=url, request_body=body, request_headers=headers
        ):
            now = datetime.now().isoformat()
            parsed_url = urlparse(url)
            try:
                request = {
                    "request": {
                        "id": request_id,
                        "method": method,
                        "url": url,
                        "body": body,
                        "headers": dict(headers),
                        "path": parsed_url.path,
                        "search": parsed_url.query,
                        "requestedAt": now,
                    }
                }
                self._request_cache[request_id] = request
            except Exception as e:
                exc_info = sys.exc_info()
                error_string = "".join(traceback.format_exception(*exc_info))
                self.log.error(
                    {
                        "request": jsonpickle.encode(request, unpicklable=False),
                        "config": jsonpickle.encode(
                            self.base_config, unpicklable=False
                        ),
                    },
                    error_string,
                    ERRORS["CACHING_REQUEST"],
                )

    def _cache_response(
        self,
        request_id,
        response_body,
        response_headers,
        response_status,
        response_status_text,
    ) -> None:
        request, response = {}, {}
        try:
            # Ignored domains are not in the request cache, so this yields None
            request = self._request_cache.pop(request_id, None)
            if request:
                decoded_body = safe_decode(response_body)
                response = {
                    "body": safe_parse_json(decoded_body),
                    "headers": dict(response_headers),
                    "status": response_status,
                    "statusText": response_status_text,
                    "respondedAt": datetime.now().isoformat(),
                }
                self._response_cache[request_id] = {
                    "request": request["request"],
                    "response": response,
                }
        except Exception as e:
            exc_info = sys.exc_info()
            error_string = "".join(traceback.format_exception(*exc_info))
            self.log.error(
                {
                    "request": jsonpickle.encode(request, unpicklable=False),
                    "response": jsonpickle.encode(response, unpicklable=False),
                    "config": jsonpickle.encode(self.base_config, unpicklable=False),
                },
                error_string,
                ERRORS["CACHING_RESPONSE"],
            )

    def close(self, *args) -> None:
        self.log.debug("Closing client auto-flush, force flushing remaining cache")
        self.flush_thread.cancel()
        self.flush_cache(force=True)

    def kill(self, *args) -> None:
        self.log.debug("Killing client auto-flush, deleting remaining cache.")
        self.flush_thread.cancel()
        self._request_cache.clear()
        self._response_cache.clear()

    def get_config(self) -> None:
        try:
            self.remote_config = parse_remote_config_json(self.api.get_config())
        except Exception as e:
            print(e)
            if self.remote_config:
                self.log.warning("Failed to update remote config")
            else:
                self.log.warning("Failed to fetch initial remote config")
            raise

    def flush_cache(self, force=False) -> None:
        if not self.remote_config:
            self.log.info("Config not loaded yet, skipping flush")
            return

        response_keys = list(self._response_cache.keys())
        request_keys = list(self._request_cache.keys())
        # If there are no responses in cache, just exit
        if len(response_keys) == 0 and not force:
            return

        # If we're forcing a flush but there's nothing in the cache, exit here
        if force and len(response_keys) == 0 and len(request_keys) == 0:
            return

        data = list(self._response_cache.values())

        if force:
            data += list(self._request_cache.values())

        data = redact_values(data, self.remote_config)
        try:
            print(f"Flushing {len(data)} items")
            self.log.debug(f"Flushing {len(data)} items")
            # self.api.post_events(data)
        except Exception as e:
            exc_info = sys.exc_info()
            error_string = "".join(traceback.format_exception(*exc_info))
            self.log.error(
                {
                    "data": jsonpickle.encode(data, unpicklable=False),
                    "config": jsonpickle.encode(self.base_config, unpicklable=False),
                },
                error_string,
                ERRORS["POSTING_EVENTS"],
            )
        finally:
            for response_key in response_keys:
                self._response_cache.pop(response_key, None)
            if force:
                for request_key in request_keys:
                    self._request_cache.pop(request_key, None)
