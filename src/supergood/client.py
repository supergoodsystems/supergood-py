#!/usr/bin/env python3

import atexit
import os
import threading
import traceback
from base64 import b64encode
from contextlib import contextmanager
from datetime import datetime
from importlib.metadata import version
from urllib.parse import urlparse

from dotenv import load_dotenv

from .api import Api
from .constants import *
from .helpers import (
    decode_headers,
    redact_all,
    redact_values,
    safe_decode,
    safe_parse_json,
)
from .logger import Logger
from .remote_config import get_vendor_endpoint_from_config, parse_remote_config_json
from .vendors.aiohttp import patch as patch_aiohttp
from .vendors.http import patch as patch_http
from .vendors.httpx import patch as patch_httpx
from .vendors.requests import patch as patch_requests
from .vendors.urllib3 import patch as patch_urllib3
from .worker import Repeater, Worker

load_dotenv()


class Client(object):
    def __init__(self):
        self.uninitialized = True

    def initialize(
        self,
        client_id=os.getenv("SUPERGOOD_CLIENT_ID"),
        client_secret_id=os.getenv("SUPERGOOD_CLIENT_SECRET"),
        base_url=os.getenv("SUPERGOOD_BASE_URL"),
        telemetry_url=os.getenv("SUPERGOOD_TELEMETRY_URL"),
        config={},
        metadata={},
    ):
        self.uninitialized = False
        # Storage for thread-local tags
        self.thread_local = threading.local()
        self.base_url = base_url if base_url else DEFAULT_SUPERGOOD_BASE_URL
        self.telemetry_url = (
            telemetry_url if telemetry_url else DEFAULT_SUPERGOOD_TELEMETRY_URL
        )

        if "serviceName" not in metadata and "SERVICE_NAME" in os.environ:
            metadata["serviceName"] = os.getenv("SERVICE_NAME")
        self.metadata = metadata

        authorization = f"{client_id}:{client_secret_id}"
        self.time_format = "%Y-%m-%dT%H:%M:%S.%fZ"

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

        # # By default will spin up threads to handle flushing and config fetching
        # #  can be changed by setting the appropriate config variable
        auto_flush = True
        auto_config = True
        if not self.base_config["runThreads"]:
            auto_flush = False
            auto_config = False

        self.api = Api(header_options, self.base_url, self.telemetry_url)
        self.api.set_event_sink_url(self.base_config["eventSinkEndpoint"])
        self.api.set_error_sink_url(self.base_config["errorSinkEndpoint"])
        self.api.set_config_pull_url(self.base_config["remoteConfigEndpoint"])
        self.api.set_telemetry_post_url(self.base_config["telemetryPostEndpoint"])
        self.log = Logger(self.__class__.__name__, self.base_config, self.api)

        self.remote_config = None
        self.remote_config_thread = Repeater(10, self._get_config)
        self.remote_config_thread.daemon = True
        if auto_config and self.base_config["useRemoteConfig"]:
            self.remote_config_thread.start()
        elif not self.base_config["useRemoteConfig"]:
            self.log.debug("Running supergood in remote config off mode!")
        else:
            self.log.debug("auto config off. Remember to request manually")

        self.api.set_logger(self.log)

        self._request_cache = {}

        # Initialize patches here
        patch_requests(self._cache_request, self._cache_response)
        patch_urllib3(self._cache_request, self._cache_response)
        patch_http(self._cache_request, self._cache_response)
        patch_aiohttp(self._cache_request, self._cache_response)
        patch_httpx(self._cache_request, self._cache_response)

        self.flush_thread = Worker(self.flush_cache)
        if auto_flush:
            self.flush_thread.start()
        else:
            self.log.debug("auto flush off, remember to flush manually")

        # Exit gracefully when possible
        atexit.register(self.close)

    def close(self) -> None:
        self.log.debug("Closing client auto-flush, force flushing remaining cache")
        self.flush_thread.flush()
        self.flush_thread.kill()
        self.remote_config_thread.cancel()

    def _build_log_payload(self, urls=None, size=None, num_events=None):
        payload = {}
        payload["config"] = self.base_config
        payload["metadata"] = self.metadata
        if urls:
            if len(urls) == 1:
                payload["metadata"].update({"requestUrl": urls[0]})
            else:
                payload["metadata"].update({"requestUrls": urls})
        if size:
            payload["metadata"].update({"payloadSize": size})
        if num_events:
            payload["numberOfEvents"] = num_events
        tags = getattr(self.thread_local, "current_tags", None)
        if tags:
            payload["metadata"]["tags"] = self._format_tags(tags)
        return payload

    def _should_ignore(
        self,
        host_domain,
        metadata,
        url=None,
        method=None,
        request_body=None,
        request_headers=None,
    ):
        supergood_base_url = urlparse(self.base_url).hostname
        supergood_telemetry_url = urlparse(self.telemetry_url).hostname
        # Logic:
        #  case 1: if we're in remote config mode and don't have one, always ignore
        #  case 2/3: ignore internal supergood calls to avoid death spiral
        #  case 4: ignore anything explicitly marked to ignore
        if (
            (self.remote_config is None and self.base_config["useRemoteConfig"])
            or host_domain == supergood_base_url
            or host_domain == supergood_telemetry_url
            or host_domain in self.base_config["ignoredDomains"]
        ):
            return True

        # At this point, if we're not in remote config mode we can safely return
        #  we really only care about the ignored domains
        if not self.base_config["useRemoteConfig"]:
            return False

        vendor, endpoint = get_vendor_endpoint_from_config(
            self.remote_config,
            url=url,
            method=method,
            request_body=request_body,
            request_headers=request_headers,
        )
        if endpoint:
            # add endpoint and vendor to metadata for quicker redaction later
            metadata["endpointId"] = endpoint.endpoint_id
            metadata["vendorId"] = vendor.vendor_id
            if endpoint.action.lower() == "ignore":
                return True
        return False

    def _cache_request(self, request_id, url, method, body, headers):
        request = {}
        try:
            url = safe_decode(url)  # we do this first so the urlparse isn't also bytes
            host_domain = urlparse(url).hostname
            safe_headers = (
                {} if headers is None else dict(headers)
            )  # sometimes headers is not json serializable
            request["metadata"] = {}
            # Check that we should cache the request
            parsed_method = safe_decode(method)
            if not self._should_ignore(
                host_domain,
                request["metadata"],  # we store endpoint id in metadata
                url=url,
                method=parsed_method,
                request_body=body,
                request_headers=safe_headers,
            ):
                now = datetime.utcnow().strftime(self.time_format)
                parsed_url = urlparse(url)
                filtered_body = (
                    ""
                    if not self.base_config["logRequestBody"]
                    else safe_parse_json(safe_decode(body))
                )
                filtered_headers = (
                    {}
                    if (not self.base_config["logRequestHeaders"] or headers is None)
                    else decode_headers(safe_headers)
                )
                request["request"] = {
                    "id": request_id,
                    "method": parsed_method,
                    "url": url,
                    "body": filtered_body,
                    "headers": filtered_headers,
                    "path": parsed_url.path,
                    "search": parsed_url.query,
                    "requestedAt": now,
                }
                tags = getattr(self.thread_local, "current_tags", None)
                if tags:
                    request["metadata"]["tags"] = self._format_tags(tags)
                self._request_cache[request_id] = request
        except Exception:
            payload = self._build_log_payload(
                urls=[url],
            )
            trace = "".join(traceback.format_exc())
            self.log.error(ERRORS["CACHING_REQUEST"], trace, payload)

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
                body = safe_parse_json(safe_decode(response_body))
                filtered_body = "" if not self.base_config["logResponseBody"] else body
                filtered_headers = (
                    {}
                    if not self.base_config["logResponseHeaders"]
                    else decode_headers(dict(response_headers))
                )
                response = {
                    "body": filtered_body,
                    "headers": filtered_headers,
                    "status": response_status,
                    "statusText": safe_decode(response_status_text),
                    "respondedAt": datetime.utcnow().strftime(self.time_format),
                }
                # Append to flush worker. If the worker is not started yet, this will start it.
                self.flush_thread.append(
                    {
                        request_id: {
                            "request": request["request"],
                            "response": response,
                            "metadata": request.get("metadata", {}),
                        }
                    }
                )
        except Exception:
            url = None
            if request and request.get("request", None):
                url = request.get("request").get("url", None)
            payload = self._build_log_payload(urls=[url] if url else [])
            trace = "".join(traceback.format_exc())
            self.log.error(ERRORS["CACHING_RESPONSE"], trace, payload)

    def kill(self) -> None:
        self.log.debug("Killing client auto-flush, deleting remaining cache.")
        self.flush_thread.kill()
        self.remote_config_thread.cancel()
        self._request_cache.clear()

    def _get_config(self) -> None:
        try:
            raw_config = self.api.get_config()
            self.remote_config = parse_remote_config_json(raw_config)
        except Exception:
            if self.remote_config:
                self.log.warning("Failed to update remote config")
            else:
                payload = self._build_log_payload()
                trace = "".join(traceback.format_exc())
                self.log.error(ERRORS["FETCHING_CONFIG"], trace, payload)

    def flush_cache(self, entries: dict) -> None:
        if self.remote_config is None and self.base_config["useRemoteConfig"]:
            self.log.info("Config not loaded yet, cannot flush")
            return

        data = list(entries.values())
        try:
            # In force redact all mode, always force redact everything
            if self.base_config["forceRedactAll"]:
                redact_all(data, self.remote_config, by_default=False)
            # In redact by default mode, redact any non-allowed keys
            elif self.base_config["redactByDefault"]:
                redact_all(data, self.remote_config, by_default=True)
            # Otherwise, redact using the remote config in remote config mode
            elif self.base_config["useRemoteConfig"]:
                to_delete = redact_values(
                    data,
                    self.remote_config,
                    self.base_config,
                )
                if to_delete:
                    data = [
                        item for (ind, item) in enumerate(data) if ind not in to_delete
                    ]
        except Exception:
            urls = []
            for entry in data:
                if entry.get("request", None):
                    urls.append(entry.get("request").get("url"))
            payload = self._build_log_payload(num_events=len(data), urls=urls)
            trace = "".join(traceback.format_exc())
            self.log.error(ERRORS["REDACTION"], trace, payload)
        else:  # Only post if no exceptions
            self.log.debug(f"Flushing {len(data)} items")
            try:
                self.api.post_telemetry(
                    {
                        "numEntries": len(entries),
                    }
                )
            except Exception as e:
                # telemetry post is nice to have, if it fails just log and ignore
                self.log.warning(f"Error posting telemetry: {e}")
            self.api.post_events(data)

    def _format_tags(self, tags):
        # takes a list of tags (dicts) and rolls them up into one dictionary
        new_tags = {}
        for tagset in tags:
            new_tags.update(tagset)
        return new_tags

    @contextmanager
    def tagging(self, tags):
        # tags should be a KV dict of primitives, e.g. {'customer': 'Patrick'}
        if self.uninitialized:
            # cannot tag when uninit, can't even log. Just yield
            try:
                yield
            finally:
                return
        #  wrap non-dicts
        if not isinstance(tags, dict):
            tags = {"tags": tags}
        current_tags = getattr(self.thread_local, "current_tags", None)
        if current_tags:
            self.thread_local.current_tags.append(tags)
        else:
            self.thread_local.current_tags = [tags]
        try:
            yield
        finally:
            self.thread_local.current_tags.pop()
