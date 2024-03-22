from urllib.parse import urljoin

import requests

from .constants import *


class Api(object):
    def __init__(
        self,
        header_options,
        base_url=DEFAULT_SUPERGOOD_BASE_URL,
        telemetry_url=DEFAULT_SUPERGOOD_TELEMETRY_URL,
    ):
        self.base_url = base_url
        self.telemetry_url = telemetry_url
        self.header_options = header_options
        self.event_sink_url = None
        self.error_sink_url = None
        self.config_pull_url = None
        self.telemetry_post_url = None

    def set_logger(self, logger):
        self.log = logger

    # Telemetry
    def set_telemetry_post_url(self, endpoint):
        self.telemetry_post_url = urljoin(self.telemetry_url, endpoint)

    # Telemetry posts are treated more as fire and forget. If they fail, no big deal
    #  this metadata primarily helps supergood debug remote issues, it's not used
    #  for anomaly/usage monitoring
    def post_telemetry(self, payload):
        if not self.telemetry_post_url:
            raise Exception(ERRORS["UNINITIALIZED"])
        response = requests.post(
            self.telemetry_post_url, json=payload, headers=self.header_options
        )
        if response.status_code == 401:
            raise Exception(ERRORS["UNAUTHORIZED"])
        if response.status_code != 200 and response.status_code != 201:
            raise Exception(ERRORS["POSTING_TELEMETRY"])
        return response.json()

    # Remote config fetching
    def set_config_pull_url(self, endpoint):
        self.config_pull_url = urljoin(self.base_url, endpoint)

    def get_config(self):
        if not self.config_pull_url:
            raise Exception(ERRORS["UNINITIALIZED"])
        response = requests.get(self.config_pull_url, headers=self.header_options)
        if response.status_code == 401:
            raise Exception(ERRORS["UNAUTHORIZED"])
        elif response.status_code != 200:
            raise Exception(ERRORS["FETCHING_CONFIG"])
        return response.json()

    # Event posting
    def set_event_sink_url(self, endpoint):
        self.event_sink_url = urljoin(self.base_url, endpoint)

    def post_events(self, payload):
        if not self.event_sink_url:
            raise Exception(ERRORS["UNINITIALIZED"])
        response = requests.post(
            self.event_sink_url, json=payload, headers=self.header_options
        )
        if response.status_code == 401:
            raise Exception(ERRORS["UNAUTHORIZED"])
        if response.status_code != 200 and response.status_code != 201:
            raise Exception(ERRORS["POSTING_EVENTS"])
        return response.json()

    # Error posting
    def set_error_sink_url(self, endpoint):
        self.error_sink_url = urljoin(self.telemetry_url, endpoint)

    def post_errors(self, data, exc_info, message):
        if not self.error_sink_url:
            raise Exception(ERRORS["UNINITIALIZED"])
        json = {"payload": data, "error": str(exc_info), "message": message}
        try:
            response = requests.post(
                self.error_sink_url, json=json, headers=self.header_options
            )
            return response.status_code
        except Exception:
            self.log.warning(f"Failed to report error to {self.error_sink_url}")
