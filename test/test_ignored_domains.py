import requests

from pytest_httpserver import HTTPServer
from .helper import get_config
from supergood import Client
from supergood.api import Api

TEST_BED_URL = 'http://supergood-testbed.herokuapp.com'
EXTERNAL_URL = 'https://api.ipify.org/?format=json'

def test_ignores_requests_to_ignored_domains(mocker):
    config = get_config(ignored_domains=['supergood-testbed.herokuapp.com'])
    mocker.patch('supergood.api.Api.post_events', return_value=None)
    mocker.patch('supergood.api.Api.post_errors', return_value=None)
    supergood_client = Client(config=config)
    requests.get(f'{TEST_BED_URL}/200')
    requests.get(f'{EXTERNAL_URL}')
    supergood_client.flush_cache()
    supergood_client.kill()
    args = Api.post_events.call_args[0][0]
    assert len(args) == 1
    assert EXTERNAL_URL == args[0]['request']['url']
