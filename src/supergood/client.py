#!/usr/bin/env python3

import atexit
import os
import traceback
from base64 import b64encode
from datetime import datetime
from importlib.metadata import version
from threading import Lock, Thread
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
from .repeating_thread import RepeatingThread
from .vendors.aiohttp import patch as patch_aiohttp
from .vendors.http import patch as patch_http
from .vendors.httpx import patch as patch_httpx
from .vendors.requests import patch as patch_requests
from .vendors.urllib3 import patch as patch_urllib3

load_dotenv()


class Client(object):
    def __init__(
        self,
        client_id=os.getenv("SUPERGOOD_CLIENT_ID"),
        client_secret_id=os.getenv("SUPERGOOD_CLIENT_SECRET"),
        base_url=os.getenv("SUPERGOOD_BASE_URL"),
        telemetry_url=os.getenv("SUPERGOOD_TELEMETRY_URL"),
        config={},
        metadata={},
    ):
        # This PID is used to detect when the client is running in a forked process
        self.main_pid = os.getpid()
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

        # By default will spin up threads to handle flushing and config fetching
        #  can be changed by setting the appropriate config variable
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
        if auto_config and self.base_config["useRemoteConfig"]:
            self.remote_config_initial_pull = Thread(
                daemon=True, target=self._get_config
            )
            self.remote_config_initial_pull.start()
        elif not self.base_config["useRemoteConfig"]:
            self.log.debug("Running supergood in remote config off mode!")
        else:
            self.log.debug("auto config off. Remember to request manually")

        self.remote_config_refresh_thread = RepeatingThread(
            self._get_config, self.base_config["configInterval"] / 1000
        )
        if auto_config and self.base_config["useRemoteConfig"]:
            self.remote_config_refresh_thread.start()

        self.api.set_logger(self.log)

        self._request_cache = {}
        self._response_cache = {}

        # Initialize patches here
        patch_requests(self._cache_request, self._cache_response)
        patch_urllib3(self._cache_request, self._cache_response)
        patch_http(self._cache_request, self._cache_response)
        patch_aiohttp(self._cache_request, self._cache_response)
        patch_httpx(self._cache_request, self._cache_response)

        self.flush_thread = RepeatingThread(
            self.flush_cache, self.base_config["flushInterval"] / 1000
        )
        self.flush_lock = Lock()
        if auto_flush:
            self.flush_thread.start()
        else:
            self.log.debug("auto flush off, remember to flush manually")

        # On clean exit, or terminated exit - exit gracefully
        if self.base_config["runThreads"]:
            atexit.register(self.close)

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
        return payload

    def _should_ignore(
        self,
        host_domain,
        metadata,
        url=None,
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
            if not self._should_ignore(
                host_domain,
                request["metadata"],  # we store endpoint id in metadata
                url=url,
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
                    "method": safe_decode(method),
                    "url": url,
                    "body": filtered_body,
                    "headers": filtered_headers,
                    "path": parsed_url.path,
                    "search": parsed_url.query,
                    "requestedAt": now,
                }
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
                if os.getpid() == self.main_pid:
                    # If we're in the main thread, push to the cache
                    self._response_cache[request_id] = {
                        "request": request["request"],
                        "response": response,
                        "metadata": request.get("metadata", {}),
                    }
                else:
                    # Otherwise, flush synchronously
                    self.sync_flush_cache(
                        [
                            {
                                "request": request["request"],
                                "response": response,
                                "metadata": request.get("metadata", {}),
                            }
                        ]
                    )

        except Exception:
            url = None
            if request and request.get("request", None):
                url = request.get("request").get("url")
            payload = self._build_log_payload(urls=[url] if url else [])
            trace = "".join(traceback.format_exc())
            self.log.error(ERRORS["CACHING_RESPONSE"], trace, payload)

    def close(self) -> None:
        self.log.debug("Closing client auto-flush, force flushing remaining cache")
        self.flush_thread.cancel()
        self.remote_config_refresh_thread.cancel()
        self.flush_cache(force=True)

    def kill(self) -> None:
        self.log.debug("Killing client auto-flush, deleting remaining cache.")
        self.flush_thread.cancel()
        self.remote_config_refresh_thread.cancel()
        self._request_cache.clear()
        self._response_cache.clear()

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

    def _take_lock(self, block=False) -> bool:
        return self.flush_lock.acquire(blocking=block)

    def _release_lock(self):
        try:
            self.flush_lock.release()
        except RuntimeError:  # releasing a non-held lock
            payload = self._build_log_payload()
            trace = "".join(traceback.format_exc())
            self.log.error(ERRORS["LOCK_STATE"], trace, payload)

    def flush_cache(self, force=False) -> None:
        # In remote config mode, don't flush until a remote config is fetched
        if self.remote_config is None and self.base_config["useRemoteConfig"]:
            self.log.info("Config not loaded yet, cannot flush")
            return

        # if we're not force flushing, and another flush is in progress, just skip
        # if we are force flushing, block until the previous flush completes.
        acquired = self._take_lock(block=force)
        if acquired == False:
            self.log.info("Flush already in progress, skipping")
            return
        # FLUSH LOCK PROTECTION START
        response_keys = []
        request_keys = []
        try:
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
                            item
                            for (ind, item) in enumerate(data)
                            if ind not in to_delete
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
                            "numResponseCacheKeys": len(response_keys),
                            "numRequestCacheKeys": len(request_keys),
                        }
                    )
                except Exception as e:
                    # telemetry post is nice to have, if it fails just log and ignore
                    self.log.warning(f"Error posting telemetry: {e}")
                self.api.post_events(data)
        except Exception:
            trace = "".join(traceback.format_exc())
            payload = ""
            try:
                urls = []
                for entry in data:
                    if entry.get("request", None):
                        urls.append(entry.get("request").get("url"))
                num_events = len(data)
                payload = self._build_log_payload(num_events=num_events, urls=urls)
            except Exception:
                # something is really messed up, just report out
                payload = self._build_log_payload()
            self.log.error(ERRORS["POSTING_EVENTS"], trace, payload)
        finally:  # always occurs, even from internal returns
            for response_key in response_keys:
                self._response_cache.pop(response_key, None)
            if force:
                for request_key in request_keys:
                    self._request_cache.pop(request_key, None)
            self.flush_lock.release()
            # FLUSH LOCK PROTECTION END

    def sync_flush_cache(self, data) -> None:
        """
        If the client detects it is running in a forked process, we probably dont
        want to spin up new threads within that fork. Instead, flush each item synchronously
        after caching the response. This does have the effect of blocking until the flush occurs
        """
        if self.remote_config is None and self.base_config["useRemoteConfig"]:
            # Forked processes get a copy of the remote config (if it has been pulled) for free
            #  however, the config fetch is expensive if it hasn't been pulled yet.
            #  not a great solution, but for now just drop the event.
            #  in the future we're planning on potentially writing these to disk for a cleanup job later
            self.log.info("Config not loaded yet, cannot flush")
            return

        # don't worry about the flush lock because each flush is only handling one event
        try:
            # don't worry about anything on the cache except for the data provided to us
            try:
                if self.base_config["forceRedactAll"]:
                    redact_all(data)
                elif self.base_config["useRemoteConfig"]:
                    to_delete = redact_values(
                        data,
                        self.remote_config,
                        self.base_config,
                    )
                    if to_delete:
                        data = [
                            item
                            for (ind, item) in enumerate(data)
                            if ind not in to_delete
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
                self.api.post_events(data)
        except Exception:
            trace = "".join(traceback.format_exc())
            try:
                urls = []
                for entry in data:
                    if entry.get("request", None):
                        urls.append(entry.get("request").get("url"))
                num_events = len(data)
                payload = self._build_log_payload(num_events=num_events, urls=urls)
            except Exception:
                # something is really messed up, just report out
                payload = self._build_log_payload()
                self.log.error(ERRORS["POSTING_EVENTS"], trace, payload)
