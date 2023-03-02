import requests
import json
from .constants import *

class Api(object):
    def __init__(self, header_options, base_url=DEFAULT_SUPERGOOD_BASE_URL):
        self.header_options = header_options
        self.config_fetch_url = base_url + 'api/config'

    def set_logger(self, logger):
        self.log = logger

    def set_event_sink_url(self, url):
        self.event_sink_url = url

    def set_error_sink_url(self, url):
        self.error_sink_url = url

    def post_events(self, payload):
        response = requests.post(self.event_sink_url, json=payload, headers=self.header_options)
        if(response.status_code == 401):
            raise Exception(ERRORS['UNAUTHORIZED'])
        if(response.status_code != 200 and response.status_code != 201):
            raise Exception(ERRORS['POSTING_EVENTS'])
        return response.json()

    def post_errors(self, data, error, message):
        json = {
            'payload': data,
            'error': error,
            'message': message
        }
        try:
            response = requests.post(self.error_sink_url, json=json, headers=self.header_options)
            return response.status_code
        except Exception as e:
            self.log.warning(f'Failed to report error to {self.error_sink_url}')

    def fetch_config(self):
        response = requests.get(self.config_fetch_url, headers=self.header_options)
        if(response.status_code == 401):
            raise Exception(ERRORS['UNAUTHORIZED'])
        if(response.status_code != 200):
            raise Exception(ERRORS['FETCHING_CONFIG'])
        return response.json()

