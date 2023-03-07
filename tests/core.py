import unittest
import sys
import requests
import time
import re
import urllib3
from urllib.parse import urlparse

from dotenv import load_dotenv
from pytest_httpserver import HTTPServer
from unittest.mock import patch
from werkzeug.wrappers import Response

from supergood import Client
from supergood.constants import ERRORS
from supergood.api import Api

from .compass_constants import *

load_dotenv()

TEST_BED_URL = 'http://supergood-testbed.herokuapp.com'

def get_config(httpserver, flush_interval=30000, keys_to_hash=[], ignored_domains=[]):
    return {
                'flushInterval': flush_interval,
                'eventSinkEndpoint': httpserver.url_for('/api/events'),
                'errorSinkEndpoint': httpserver.url_for('/api/errors'),
                'keysToHash': keys_to_hash,
                'ignoredDomains': ignored_domains
            }

class SupergoodTestCase(unittest.TestCase):

    def test_captures_all_outgoing_200_http_requests(self):
        CALL_COUNT = 5
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))
            with patch.object(Api, 'post_events') as mocked_events:
                for i in range(CALL_COUNT):
                    requests.get(f'{TEST_BED_URL}/200')
                self.client.close()

            args = mocked_events.call_args[0][0]
            assert len(args) == CALL_COUNT

    def test_captures_non_success_status_and_errors(self):
        http_error_codes = [400, 401, 403, 404, 500, 501, 502, 503, 504]
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                for code in http_error_codes:
                    requests.get(f'{TEST_BED_URL}/{code}')
                self.client.close()

            args = mocked_events.call_args[0][0]
            assert len(args) == len(http_error_codes)

            responded_codes = set(map(lambda x: x['response']['status'], args))
            assert responded_codes == set(http_error_codes)

    def test_post_requests(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                response = requests.post(f'{TEST_BED_URL}/200?payload=value')
                response.raise_for_status()
                json = response.json()
                self.client.close()

            assert json['payload'] == 'value'
            args = mocked_events.call_args[0][0]
            assert len(args) == 1


    def test_post_request_for_large_payload(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                response = requests.post(URL, headers=HEADERS, json=PAYLOAD)
                response.raise_for_status()
                json = response.json()
                self.client.close()

            assert json.get("mapResults", {}).get("totalItems", 0) >= 0
            args = mocked_events.call_args[0][0]
            assert len(args) == 1

    def test_hanging_response(self):
        HANG_TIME_IN_SECONDS = 2
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))
            with patch.object(Api, 'post_events') as mocked_events:
                requests.get(f'{TEST_BED_URL}/200?sleep={HANG_TIME_IN_SECONDS}')
                self.client.close()

            args = mocked_events.call_args[0][0]
            assert len(args) == 1

    def test_posting_errors(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            def mocked_post_events(_self, request):
                raise Exception('mocked post events error')

            with patch.object(Api, 'post_events', mocked_post_events):
                with patch.object(Api, 'post_errors') as mocked_errors:
                    requests.get(f'{TEST_BED_URL}/200')
                    self.client.close()

                error_message = mocked_errors.call_args[0][2]
                assert error_message == ERRORS['POSTING_EVENTS']


    def test_hashing_entire_body_from_config(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, keys_to_hash=['response.body'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                requests.get(f'{TEST_BED_URL}/200?hash_me=abc&dont_hash_me=def')
                self.client.close()

            args = mocked_events.call_args[0][0]
            # Regex to match a base64 encoded string
            assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['hashed']) is not None

    def test_hashing_single_field_in_body_from_config(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, keys_to_hash=['response.body.hash_me', 'response.body.i_dont_exist'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                requests.get(f'{TEST_BED_URL}/200?hash_me=abc&dont_hash_me=def')
                self.client.close()

            args = mocked_events.call_args[0][0]
            # Regex to match a base64 encoded string
            assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['hash_me']) is not None

    def test_accepts_requests_to_non_ignored_domains(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, ignored_domains=[])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                requests.get(f'{TEST_BED_URL}/200')
                self.client.close()

            args = mocked_events.call_args[0][0][0]
            assert f'{TEST_BED_URL}/200' == args['request']['url']

    def test_ignores_requests_to_ignored_domains(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, ignored_domains=['supergood-testbed.herokuapp.com'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                requests.get(f'{TEST_BED_URL}/200')
                self.client.close()

            mocked_events.assert_not_called()

    def test_different_http_library(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))
            with patch.object(Api, 'post_events') as mocked_events:
                http = urllib3.PoolManager()
                http.request('GET', f'{TEST_BED_URL}/200')
                self.client.close()

            args = mocked_events.call_args[0][0]
            assert len(args) == 1

def suite_success_states():
    suite = unittest.TestSuite()
    suite.addTest(SupergoodTestCase('test_captures_all_outgoing_200_http_requests'))
    suite.addTest(SupergoodTestCase('test_captures_non_success_status_and_errors'))
    return suite

def suite_failure_states():
    suite = unittest.TestSuite()
    suite.addTest(SupergoodTestCase('test_hanging_response'))
    suite.addTest(SupergoodTestCase('test_posting_errors'))
    return suite

def suite_config_specifications():
    suite = unittest.TestSuite()
    suite.addTest(SupergoodTestCase('test_hashing_entire_body_from_config'))
    suite.addTest(SupergoodTestCase('test_hashing_single_field_in_body_from_config'))
    suite.addTest(SupergoodTestCase('test_ignores_requests_to_ignored_domains'))
    suite.addTest(SupergoodTestCase('test_accepts_requests_to_non_ignored_domains'))
    return suite

def suite_test_different_http_library():
    suite = unittest.TestSuite()
    suite.addTest(SupergoodTestCase('test_different_http_library'))
    return suite

def suite_test_post_requests():
    suite = unittest.TestSuite()
    suite.addTest(SupergoodTestCase('test_post_request_for_large_payload'))
    suite.addTest(SupergoodTestCase('test_post_requests'))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite_success_states())
    runner.run(suite_failure_states())
    runner.run(suite_config_specifications())
    runner.run(suite_test_different_http_library())
    runner.run(suite_test_post_requests())

