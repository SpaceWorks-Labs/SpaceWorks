from copy import deepcopy

import pytest
from rest_framework.test import APIClient

from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.notification_slack import workspace_identity
from tests.accounts.reauth_helpers import reauthenticate
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db

CREDS = {
    "slack": {"client_id": "123", "client_secret": "secret", "signing_secret": "sign"},
    "mattermost": {"server_url": "https://chat.example", "bot_token": "bot", "client_id": "a" * 26,
                   "client_secret": "secret", "webhook_token": "webhook"},
    "discord": {"application_id": "123", "guild_id": "456", "public_key": "a" * 64,
                "bot_token": "bot", "client_secret": "secret"},
    "twilio": {"account_sid": "AC" + "a" * 32, "auth_token": "b" * 32,
               "whatsapp_sender": "+14155550100", "public_base_url": "https://api.example"},
}


@pytest.fixture
def manager(monkeypatch):
    # DNS resolution is separately tested by the adapter's SSRF suite.
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.resolve_server", lambda *_: None)
    space = make_space("review2-providers")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "slack", "mattermost", "discord"})
    space.save(update_fields=["enabled_modules"])
    user = make_member("review2-manager", space)
    api = APIClient()
    reauthenticate(api, user)  # Credential writes require the real step-up.
    return space, api


def patch(manager, provider, values, **extra):
    space, api = manager
    channel = "whatsapp" if provider == "twilio" else provider
    return api.patch(f"/api/v1/integrations/makerspace/{space.pk}/channels/{channel}",
                     {"provider": provider, "credentials": values, **extra}, format="json")


@pytest.mark.parametrize("provider,key", [(p, k) for p, values in CREDS.items() for k in values])
def test_missing_required_credentials_return_typed_400_and_rollback(manager, provider, key):
    values = deepcopy(CREDS[provider])
    values.pop(key)
    response = patch(manager, provider, values)
    assert response.status_code == 400
    assert response.data["code"] == "invalid_credentials"
    assert not ChannelConfiguration.objects.filter(makerspace=manager[0]).exists()
    assert "secret" not in str(response.data)


@pytest.mark.parametrize("provider", CREDS)
def test_valid_credentials_save_without_exposing_secrets(manager, provider):
    response = patch(manager, provider, CREDS[provider])
    assert response.status_code == 200, response.data
    channel = "whatsapp" if provider == "twilio" else provider
    config = ChannelConfiguration.objects.get(makerspace=manager[0], channel=channel)
    assert config.get_credentials() == CREDS[provider]
    assert "credentials" not in response.data
    if provider in {"discord", "mattermost"}:
        assert config.integration_identity == ("123:456" if provider == "discord" else "https://chat.example")


@pytest.mark.parametrize("origin", ["http://api.example", "https://api.example/path", "https://u:p@api.example", "https://api.example?secret=1"])
def test_twilio_refuses_non_https_origins(manager, origin):
    assert patch(manager, "twilio", {**CREDS["twilio"], "public_base_url": origin}).status_code == 400


@pytest.mark.parametrize("provider", ["slack", "mattermost", "discord"])
def test_typed_identity_cannot_disagree_with_provider_credentials(manager, provider):
    assert patch(manager, provider, CREDS[provider], integration_identity="typed-id").status_code == 400


def test_slack_bootstrap_cannot_enable_personal_delivery_until_installed(manager):
    assert patch(manager, "slack", CREDS["slack"], personal_enabled=True).status_code == 400
    values = {**CREDS["slack"], "team_id": "T123", "bot_token": "xoxb-token"}
    response = patch(manager, "slack", values, integration_identity=workspace_identity("T123"), personal_enabled=True)
    assert response.status_code == 200
    space, api = manager
    config = ChannelConfiguration.objects.get(makerspace=space, channel="slack")
    generation = config.generation
    response = api.patch(f"/api/v1/integrations/makerspace/{space.pk}/channels/slack", {"room_enabled": False}, format="json")
    assert response.status_code == 200 and response.data["generation"] == generation


def test_unrelated_toggle_does_not_revalidate_or_rotate_existing_credentials(manager):
    space, api = manager
    config = ChannelConfiguration.objects.create(makerspace=space, channel="slack", provider="slack",
        personal_enabled=True, integration_identity="legacy-workspace", generation=7)
    config.set_credentials({"legacy": "secret"})
    config.save()
    response = api.patch(f"/api/v1/integrations/makerspace/{space.pk}/channels/slack",
                         {"room_enabled": False, "personal_enabled": True}, format="json")
    assert response.status_code == 200 and response.data["generation"] == 7
    config.refresh_from_db()
    assert config.get_credentials() == {"legacy": "secret"}
    rejected = patch(manager, "slack", {"client_id": "incomplete"})
    assert rejected.status_code == 400 and rejected.data["code"] == "invalid_credentials"
    config.refresh_from_db()
    assert config.generation == 7 and config.get_credentials() == {"legacy": "secret"}
