import pytest

from supergood import Client
from tests.helper import get_config, get_remote_config


@pytest.fixture(scope="session")
def broken_redaction(session_mocker):
    session_mocker.patch(
        "supergood.client.redact_values", side_effect=Exception
    ).start()
    yield session_mocker


@pytest.fixture(scope="session")
def monkeysession():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture(scope="session")
def broken_client(broken_redaction, monkeysession):
    config = get_config()
    remote_config = get_remote_config()
    broken_redaction.patch("supergood.api.Api.post_events", return_value=None).start()
    broken_redaction.patch("supergood.api.Api.post_errors", return_value=None).start()
    broken_redaction.patch(
        "supergood.api.Api.get_config", return_value=remote_config
    ).start()
    client = Client(
        client_id="client_id",
        client_secret_id="client_secret_id",
        base_url="https://api.supergood.ai",
        telemetry_url="https://telemetry.supergood.ai",
        config=config,
    )
    monkeysession.setenv("SG_OVERRIDE_AUTO_FLUSH", "false")
    monkeysession.setenv("SG_OVERRIDE_AUTO_CONFIG", "false")
    client._get_config()
    yield client
    client.kill()  # on exit


@pytest.fixture(scope="session")
def supergood_client(request, session_mocker, monkeysession):
    # Allows for a param dictionary to control behavior
    # currently looks for "config" "remote_config" and "auto"
    config = get_config()
    auto = False
    remote_config = get_remote_config()
    if getattr(request, "param", None):
        if request.param.get("config", None):
            config = request.param["config"]
        if request.param.get("remote_config", None):
            remote_config = request.param["remote_config"]
        if request.param.get("auto", None):
            auto = request.param["auto"]

    session_mocker.patch("supergood.api.Api.post_events", return_value=None).start()
    session_mocker.patch("supergood.api.Api.post_errors", return_value=None).start()
    session_mocker.patch(
        "supergood.api.Api.get_config", return_value=remote_config
    ).start()
    session_mocker.patch("supergood.api.Api.post_telemetry", return_value=None).start()

    if not auto:
        monkeysession.setenv("SG_OVERRIDE_AUTO_FLUSH", "false")
        monkeysession.setenv("SG_OVERRIDE_AUTO_CONFIG", "false")

    client = Client(
        client_id="client_id",
        client_secret_id="client_secret_id",
        base_url="https://api.supergood.ai",
        telemetry_url="https://telemetry.supergood.ai",
        config=config,
    )
    client._get_config()
    yield client
    client.kill()  # on exit
