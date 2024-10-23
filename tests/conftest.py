from unittest.mock import MagicMock

import pytest

from supergood import Client
from tests.helper import get_config, get_remote_config


@pytest.fixture(scope="function")
def monkeysession():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture
def supergood_client(request, mocker):
    with pytest.MonkeyPatch.context() as mp:
        config = get_config()
        remote_config = get_remote_config()

        if getattr(request, "param", None):
            if request.param.get("config", None):
                config = request.param["config"]
            if request.param.get("remote_config", None):
                remote_config = request.param["remote_config"]

        Client.initialize(
            client_id="client_id",
            client_secret_id="client_secret_id",
            base_url="https://api.supergood.ai",
            telemetry_url="https://telemetry.supergood.ai",
            config=config,
        )
        # first 3 are just to make sure we don't post anything externally
        mocker.patch("supergood.api.Api.post_events", return_value=None).start()
        mocker.patch("supergood.api.Api.post_errors", return_value=None).start()
        mocker.patch("supergood.api.Api.post_telemetry", return_value=None).start()
        # next we make sure we don't call get externally, and stub in our remote config
        mocker.patch("supergood.api.Api.get_config", return_value=remote_config).start()
        # Turns off the worker, pytest mocks don't always play well with threads
        mocker.patch("supergood.worker.Worker.start", return_value=None).start()
        mocker.patch("supergood.worker.Repeater.start", return_value=None).start()
        mocker.patch("supergood.worker.Worker.append", return_value=True).start()
        mp.setenv("SG_OVERRIDE_AUTO_FLUSH", "false")
        mp.setenv("SG_OVERRIDE_AUTO_CONFIG", "false")
        Client._get_config()
        yield Client
        Client.kill()
