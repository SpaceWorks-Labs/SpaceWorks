from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.integrations.notification_slack import SlackProvider
from apps.integrations.notification_mattermost import MattermostProvider
from apps.integrations.notification_discord import DiscordProvider
from apps.integrations.notification_slack_http import ProviderFailure

PROVIDERS = {"slack": SlackProvider, "mattermost": MattermostProvider, "discord": DiscordProvider}
pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("channel", PROVIDERS)
def test_personal_delivery_opens_dm_then_sends_with_stable_identity(chat, channel, monkeypatch):
    c = chat(channel)
    if channel == "slack":
        fake = Mock(side_effect=[{"team_id": "T123"}, {"channel": {"id": "D123"}}, {"ts": "123.456"}] * 2)
        monkeypatch.setattr("apps.integrations.notification_slack.slack_api", fake)
    elif channel == "mattermost":
        fake = Mock(side_effect=[{"id": "b" * 26, "is_bot": True}, {"id": "a" * 26},
                                {"id": "channel"}, {"id": "message"}] * 2)
        monkeypatch.setattr("apps.integrations.notification_mattermost.mattermost_api", fake)
    else:
        fake = Mock(side_effect=[{"id": "111"}, {"id": "message"}] * 2)
        monkeypatch.setattr("apps.integrations.notification_discord.api", fake)
    provider = PROVIDERS[channel](c.config)
    assert provider.send(c.delivery, {"text": "Private body"}).accepted
    first = fake.call_args.kwargs["data"]
    assert provider.send(c.delivery, {"text": "Private body"}).accepted
    assert first == fake.call_args.kwargs["data"]
    assert "Private body" in first.values()


@pytest.mark.parametrize("channel", PROVIDERS)
@pytest.mark.parametrize("code,retryable", [("invalid_endpoint", False), ("rate_limited", True), ("timeout", True)])
def test_delivery_errors_are_sanitized_and_preserve_retry_metadata(chat, channel, code, retryable, monkeypatch):
    c = chat(channel)
    target = {"slack": "slack_api", "mattermost": "mattermost_api", "discord": "api"}[channel]
    monkeypatch.setattr(f"apps.integrations.notification_{channel}.{target}",
        Mock(side_effect=ProviderFailure(code, retryable=retryable, retry_after=17,
                                        ambiguous=code == "timeout")))
    result = PROVIDERS[channel](c.config).send(c.delivery, {"text": "private"})
    assert not result.accepted and result.retryable == retryable
    assert result.error_code == code and result.retry_after == 17
    assert result.ambiguous == (code == "timeout")


@pytest.mark.parametrize("channel", PROVIDERS)
def test_generation_rotation_invalidates_endpoint_before_network(chat, channel):
    c = chat(channel)
    provider = PROVIDERS[channel](c.config)
    type(c.config).objects.filter(pk=c.config.pk).update(generation=c.config.generation + 1)
    result = provider.send(c.delivery, {"text": "private"})
    assert not result.accepted and result.error_code == "invalid_endpoint"


@pytest.mark.parametrize("channel", PROVIDERS)
@pytest.mark.parametrize("destination", [False, True])
def test_room_provider_preserves_legacy_webhook_call(chat, channel, destination, monkeypatch):
    c = chat(channel)
    room = SimpleNamespace(makerspace_id=c.space.pk, channel=channel, is_active=True) if destination else None
    fake = Mock(return_value=True)
    monkeypatch.setattr("apps.integrations.webhooks.send_webhook", fake)
    result = PROVIDERS[channel](c.config).send_room("Staff summary", room)
    assert result.accepted
    fake.assert_called_once_with(c.space, channel=channel, text="Staff summary", destination=room)


@pytest.mark.parametrize("channel", PROVIDERS)
def test_room_disabled_refuses_without_falling_back(chat, channel):
    c = chat(channel)
    c.config.room_enabled = False
    c.config.save(update_fields=["room_enabled"])
    assert not PROVIDERS[channel](c.config).send_room("private").accepted


@pytest.mark.parametrize("channel", PROVIDERS)
def test_unexpected_provider_failure_has_no_private_logging(chat, channel, monkeypatch, caplog):
    c = chat(channel)
    target = {"slack": "slack_api", "mattermost": "mattermost_api", "discord": "api"}[channel]
    monkeypatch.setattr(f"apps.integrations.notification_{channel}.{target}",
        Mock(side_effect=RuntimeError("private-bot-token Private body U123")))
    result = PROVIDERS[channel](c.config).send(c.delivery, {"text": "Private body"})
    assert result.error_code == "provider_error"
    assert not result.retryable
    assert all(secret not in caplog.text for secret in ("private-bot-token", "Private body", "U123"))
