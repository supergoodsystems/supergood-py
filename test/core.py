import unittest
import sys
import requests
import time
import re
import urllib3

from dotenv import load_dotenv
from pytest_httpserver import HTTPServer
from unittest.mock import patch
from werkzeug.wrappers import Response


sys.path.append('/Users/alexklarfeld/Projects/supergood-systems')

from supergood_py import Client
from supergood_py.constants import ERRORS
from supergood_py.api import Api

load_dotenv()


def get_config(httpserver, flush_interval=30, keys_to_hash=[], ignored_domains=[]):
    return {
                'flush_interval': flush_interval,
                'event_sink_endpoint': httpserver.url_for('/api/events'),
                'error_sink_endpoint': httpserver.url_for('/api/errors'),
                'keys_to_hash': keys_to_hash,
                'ignored_domains': ignored_domains
            }

class SupergoodTestCase(unittest.TestCase):

    def test_captures_all_outgoing_200_http_requests(self):
        CALL_COUNT = 5
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                outbound_server.expect_request('/200').respond_with_json({ 'success': True }, status=200)
                with patch.object(Api, 'post_events') as mocked_events:
                    for i in range(CALL_COUNT):
                        requests.get(outbound_server.url_for('/200'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                assert len(args) == CALL_COUNT

    def test_captures_non_success_status_and_errors(self):
        http_error_codes = [400, 401, 403, 404, 500, 501, 502, 503, 504]
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                with patch.object(Api, 'post_events') as mocked_events:
                    for code in http_error_codes:
                        outbound_server.expect_request(f'/{code}').respond_with_json({ 'success': False }, status=code)
                        requests.get(outbound_server.url_for(f'/{code}'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                assert len(args) == len(http_error_codes)

                responded_codes = set(map(lambda x: x['response']['status'], args))
                assert responded_codes == set(http_error_codes)

    def test_hanging_response(self):
        HANG_TIME_IN_SECONDS = 2
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                def hanging_handler(request):
                    time.sleep(HANG_TIME_IN_SECONDS)
                    return Response(status=200)

                outbound_server.expect_request('/hang').respond_with_handler(hanging_handler)

                with patch.object(Api, 'post_events') as mocked_events:
                    requests.get(outbound_server.url_for('/hang'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                assert len(args) == 1

    def test_posting_errors(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                def mocked_post_events(_self, request):
                    raise Exception('mocked post events error')

                outbound_server.expect_request('/generate-error').respond_with_json({ 'success': True }, status=200)
                with patch.object(Api, 'post_events', mocked_post_events):
                    with patch.object(Api, 'post_errors') as mocked_errors:
                        requests.get(outbound_server.url_for('/generate-error'))
                        self.client.close()

                error_message = mocked_errors.call_args[0][2]
                assert error_message == ERRORS['POSTING_EVENTS']


    def test_hashing_entire_body_from_config(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, keys_to_hash=['response.body'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                outbound_server.expect_request('/200').respond_with_json({ 'success': True }, status=200)
                with patch.object(Api, 'post_events') as mocked_events:
                    requests.get(outbound_server.url_for('/200'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                # Regex to match a base64 encoded string
                assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['hashed']) is not None

    def test_hashing_single_field_in_body_from_config(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, keys_to_hash=['response.body.keys.hash_me', 'response.body.keys.i_dont_exist'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                outbound_server.expect_request('/200').respond_with_json({ 'keys': { 'hash_me': 'abc', 'dont_hash_me': 'def '} }, status=200)
                with patch.object(Api, 'post_events') as mocked_events:
                    requests.get(outbound_server.url_for('/200'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                # Regex to match a base64 encoded string
                assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['keys']['hash_me']) is not None
                assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['body']['keys']['dont_hash_me']) is None

    def test_hashing_headers_from_config(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, keys_to_hash=['request.headers', 'response.headers.X-Test-Header'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                outbound_server.expect_request('/200').respond_with_json({ 'success': True }, status=200, headers={'X-Test-Header': 'abc'})
                with patch.object(Api, 'post_events') as mocked_events:
                    requests.get(outbound_server.url_for('/200'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                # Regex to match a base64 encoded string
                assert re.match(r'^[A-Za-z0-9+/]+[=]{0,2}$', args[0]['response']['headers']['X-Test-Header']) is not None

    def test_accepts_requests_to_non_ignored_domains(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, ignored_domains=[])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                requests.get('http://supergood-testbed.herokuapp.com/200')
                self.client.close()

            args = mocked_events.call_args[0][0][0]
            assert 'http://supergood-testbed.herokuapp.com:80/200' == args['request']['url']

    def test_ignores_requests_to_ignored_domains(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver, ignored_domains=['supergood-testbed.herokuapp.com'])
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with patch.object(Api, 'post_events') as mocked_events:
                requests.get('http://supergood-testbed.herokuapp.com/200')
                self.client.close()

            mocked_events.assert_not_called()

    def test_different_http_library(self):
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                outbound_server.expect_request('/200').respond_with_json({ 'success': True }, status=200)
                with patch.object(Api, 'post_events') as mocked_events:
                    http = urllib3.PoolManager()
                    http.request('GET', outbound_server.url_for('/200'))
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
    suite.addTest(SupergoodTestCase('test_hashing_headers_from_config'))
    suite.addTest(SupergoodTestCase('test_ignores_requests_to_ignored_domains'))
    suite.addTest(SupergoodTestCase('test_accepts_requests_to_non_ignored_domains'))
    return suite

def suite_test_different_http_library():
    suite = unittest.TestSuite()
    suite.addTest(SupergoodTestCase('test_different_http_library'))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite_success_states())
    runner.run(suite_failure_states())
    runner.run(suite_config_specifications())
    runner.run(suite_test_different_http_library())

