from datetime import timedelta
from types import SimpleNamespace
import socket

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from apps.integrations.notification_proofs import digest
from apps.integrations.notification_slack import workspace_identity
from tests.return_helpers import make_member, make_space


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("Provider tests must mock the network")
    # Isolate provider networking without disabling the test runner's Redis cache
    # (throttles) or PostgreSQL connections.
    monkeypatch.setattr("apps.integrations.notification_slack_http.resolve_webhook_target", refused)
    monkeypatch.setattr("apps.integrations.notification_slack_http._PinnedHTTPSConnection.connect", refused)
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.socket", SimpleNamespace(
        AF_INET=socket.AF_INET, AF_INET6=socket.AF_INET6, SOCK_STREAM=socket.SOCK_STREAM,
        getaddrinfo=refused))


@pytest.fixture
def chat(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.NOTIFICATION_SLACK_REDIRECT_URI = "https://console.example/slack/oauth/callback"
    settings.NOTIFICATION_MATTERMOST_REDIRECT_URI = "https://console.example/mattermost/oauth/callback"
    settings.NOTIFICATION_DISCORD_REDIRECT_URI = "https://console.example/discord/oauth/callback"
    def build(channel):
        space = make_space(f"p2-chat-{channel}")
        space.enabled_modules = sorted(set(space.enabled_modules or []) | {
            "notifications", "slack", "mattermost", "discord", "membership"})
        space.save(update_fields=["enabled_modules"])
        user = make_member(f"p2-{channel}", space)
        identity = {"slack": workspace_identity("T123"), "mattermost": "https://chat.example", "discord": "123:456"}[channel]
        config = ChannelConfiguration.objects.create(makerspace=space, channel=channel, provider=channel,
            enabled=True, room_enabled=True, personal_enabled=True, integration_identity=identity)
        creds = {"bot_token": "private-bot-token", "client_id": "app-id", "client_secret": "secret",
            "signing_secret": "signing-secret", "server_url": "https://chat.example",
            "application_id": "123", "guild_id": "456", "public_key": "00" * 32, "webhook_token": "mm-secret",
            "team_id": "T123"}
        config.set_credentials(creds)
        config.save(update_fields=["credentials"])
        destination = {"slack": "U123", "mattermost": "a" * 26, "discord": "789"}[channel]
        endpoint = NotificationEndpoint.objects.create(makerspace=space, user=user, configuration=config,
            channel=channel, provider=channel, destination=destination, provider_subject=destination,
            identity_digest="a" * 64, integration_identity=identity, integration_generation=config.generation,
            verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
        def challenge():
            code = "secret-state-proof"
            row = NotificationEndpointChallenge.objects.create(makerspace=space, user=user, configuration=config,
                integration_generation=config.generation, integration_identity=identity, code_digest=digest(code),
                expires_at=timezone.now() + timedelta(minutes=10), consented_at=timezone.now(), consent_version="v1")
            return row, code
        return SimpleNamespace(space=space, user=user, config=config, endpoint=endpoint, creds=creds,
            challenge=challenge, delivery=SimpleNamespace(pk=170, endpoint=endpoint))
    return build
