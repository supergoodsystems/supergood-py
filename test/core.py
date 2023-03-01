import unittest
import sys
import requests

from dotenv import load_dotenv
from pytest_httpserver import HTTPServer
from unittest.mock import patch

sys.path.append('/Users/alexklarfeld/Projects/supergood-systems')

from supergood_py import Client
from supergood_py.constants import DEFAULT_SUPERGOOD_CONFIG_URL, DEFAULT_SUPERGOOD_CONFIG
from supergood_py.api import Api

load_dotenv()


def get_config(httpserver):
    return {
                'flush_interval': 30,
                'event_sink_endpoint': httpserver.url_for('/api/events'),
                'error_sink_endpoint': httpserver.url_for('/api/errors'),
                'keys_to_hash': ['request.body', 'response.body'],
                'ignored_domains': []
            }

class SupergoodTestCase(unittest.TestCase):
    def test_captures_all_outgoing_200_http_requests(self):
        CALL_COUNT = 5
        with HTTPServer() as httpserver:
            config = get_config(httpserver)
            httpserver.expect_request('/api/config').respond_with_json(config)
            self.client = Client(base_url=httpserver.url_for('/'))

            with HTTPServer() as outbound_server:
                outbound_server.expect_request('/200').respond_with_json({ 'success': True })

                with patch.object(Api, 'post_events') as mocked_events:
                    for i in range(CALL_COUNT):
                        response = requests.get(outbound_server.url_for('/200'))
                    self.client.close()

                args = mocked_events.call_args[0][0]
                assert len(args) == CALL_COUNT




    # 'testing success states'
    #     'captures all outgoing 200 http requests'
    #     'captures non-success status and errors'

    # 'testing failure states'
    #     'hanging response'
    #     'posting errors'

    # 'config specifications'
    #     'hashing'
    #     'not hashing'
    #     'keys to hash not in config'
    #     'ignores requests to ignored domains'
    #     'operates normally when ignored domains is empty'

    # 'testing various endpoints and libraries basic functionality'
    #     '<different http libraries>'

    def tearDown(self):
        self.client.close()
# def test_success_states_suite():
#     suite = unittest.TestSuite()
#     suite.addTest(SupergoodTestCase('test_captures_all_outgoing_200_http_requests'))
#     suite.addTest(SupergoodTestCase('test_captures_non_success_status_and_errors'))
#     return suite

if __name__ == '__main__':
    unittest.main()

