import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from rest_framework.test import APIClient

from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.notification_proofs import start
from tests.return_helpers import make_member, make_space


@pytest.fixture(autouse=True)
def telegram_environment(settings, monkeypatch):
    settings.TELEGRAM_WEBHOOK_SECRET = "telegram-proof-secret"
    settings.TELEGRAM_API_URL = "https://telegram.invalid"
    # Every test must explicitly opt in to mocked network responses.
    blocked = Mock(side_effect=AssertionError("Unexpected outbound network call"))
    monkeypatch.setattr("urllib.request.urlopen", blocked)
    return blocked


@pytest.fixture
def bot_http(monkeypatch):
    responses, calls = [], []

    def urlopen(request, timeout):
        calls.append((request, timeout))
        outcome = responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps(outcome).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return SimpleNamespace(responses=responses, calls=calls)


@pytest.fixture
def telegram_account():
    space = make_space("p2-telegram")
    user = make_member("telegram-owner", space)
    config = ChannelConfiguration.objects.create(makerspace=space, channel="telegram", provider="telegram",
        enabled=True, personal_enabled=True, room_enabled=True, integration_identity="telegram-installation")
    config.set_credentials({"bot_token": "12345:private-token"})
    config.save(update_fields=["credentials"])
    return SimpleNamespace(space=space, user=user, config=config)


@pytest.fixture
def begin(telegram_account, bot_http):
    def create():
        bot_http.responses.append({"ok": True, "result": {"id": 12345, "is_bot": True, "username": "SpaceWorksBot"}})
        challenge, response = start(telegram_account.user, telegram_account.config, "v1")
        code = parse_qs(urlsplit(response["connect_url"]).query)["start"][0]
        return challenge, code, response
    return create


@pytest.fixture
def webhook():
    def post(code=None, *, body=None, secret="telegram-proof-secret"):
        payload = body if body is not None else {"update_id": 1, "message": {
            "text": f"/start {code}", "chat": {"id": 789, "type": "private"},
            "from": {"id": 789, "is_bot": False},
        }}
        return APIClient().post("/api/v1/integrations/telegram/webhook", payload, format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret)
    return post
