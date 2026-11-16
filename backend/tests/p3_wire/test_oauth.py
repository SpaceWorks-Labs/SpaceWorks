from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_providers import CallbackEvent, EndpointProof
from apps.integrations.notification_slack_oauth import read_state, redirect_uri, state_for

pytestmark = pytest.mark.django_db
CHANNELS = ["slack", "mattermost", "discord"]


def verify_url(world, challenge):
    return reverse("contract-endpoint-verify", kwargs={"makerspace_id": world.space.pk, "challenge_id": challenge.pk})


def fake_oauth(monkeypatch, channel):
    classes = {"slack": "SlackProvider", "mattermost": "MattermostProvider", "discord": "DiscordProvider"}
    calls = []
    def prove(provider, data, user_id=None):
        row, code = read_state(provider.config, data["state"], user_id=user_id)
        calls.append((row.pk, user_id))
        return CallbackEvent(proof=EndpointProof(code, "private-id", provider.config.integration_identity,
                                                "private-subject", private=True))
    monkeypatch.setattr(f"apps.integrations.notification_{channel}.{classes[channel]}.oauth_proof", prove)
    return calls


@pytest.mark.parametrize("channel", CHANNELS)
def test_authenticated_verify_consumes_proof_once_and_audits(world, channel, monkeypatch):
    config = world.config(channel)
    row, code = world.challenge(config)
    calls = fake_oauth(monkeypatch, channel)
    payload = {"code": "provider-code", "state": state_for(row, code)}
    client = world.client(world.owner, jwt=True)
    response = client.post(verify_url(world, row), payload, format="json")
    assert response.status_code == 200, response.data
    endpoint = NotificationEndpoint.objects.get(pk=response.data["id"])
    assert endpoint.user_id == world.owner.pk and endpoint.destination == "private-id"
    row.refresh_from_db()
    assert row.consumed_at and row.endpoint_id == endpoint.pk
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=world.space, actor=world.owner, action="notification.endpoint_verified").exists()
    assert client.post(verify_url(world, row), payload, format="json").status_code == 400
    assert len(calls) == 1


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("failure", ["wrong_challenge", "wrong_user", "expired", "rotation", "tamper", "missing_state"])
def test_oauth_rejects_unbound_proofs_before_exchange(world, channel, failure, monkeypatch):
    config = world.config(channel)
    row, code = world.challenge(config)
    state = state_for(row, code)
    actor = world.owner
    if failure == "wrong_challenge":
        row, _ = world.challenge(config)
    elif failure == "wrong_user":
        actor = world.other
    elif failure == "expired":
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save(update_fields=["expires_at"])
    elif failure == "rotation":
        config.generation += 1
        config.save(update_fields=["generation"])
    elif failure == "tamper":
        state += "changed"
    else:
        state = ""
    calls = fake_oauth(monkeypatch, channel)
    response = world.client(actor).post(verify_url(world, row), {"code": "provider-code", "state": state}, format="json")
    assert response.status_code in (400, 404), response.data
    assert calls == [] and not NotificationEndpoint.objects.filter(configuration=config).exists()


@pytest.mark.parametrize("channel", CHANNELS)
def test_anonymous_and_old_callbacks_cannot_complete_personal_oauth(world, channel, monkeypatch):
    config = world.config(channel)
    row, code = world.challenge(config)
    payload = {"code": "provider-code", "state": state_for(row, code)}
    calls = fake_oauth(monkeypatch, channel)
    assert world.client().post(verify_url(world, row), payload, format="json").status_code == 401
    callback = reverse(f"notification-{channel}-oauth", kwargs={"makerspace_id": world.space.pk})
    assert world.client().get(callback, payload).status_code == 401
    assert world.client(world.owner).post(callback, payload, format="json").status_code == 400
    assert calls == []


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("uri", ["", "http://app.example.test/member/inbox", "https://a:b@app.example.test/inbox", "https://app.example.test/inbox#fragment"])
def test_redirect_configuration_fails_closed(settings, channel, uri):
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", uri)
    with pytest.raises(ValidationError):
        redirect_uri(channel, 2, 3)


@pytest.mark.parametrize("channel", CHANNELS)
def test_frontend_redirect_contract_refuses_dynamic_placeholders(settings, channel):
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI",
            "https://app.example.test/m/{makerspace_id}/member/inbox?notify_challenge={challenge_id}&tab=channels")
    with pytest.raises(ValidationError):
        redirect_uri(channel, 12, 34)


@pytest.mark.parametrize("channel", CHANNELS)
def test_bot_authentication_failure_never_revokes_connections(world, channel, monkeypatch):
    from apps.integrations.notification_providers import provider_for
    from apps.integrations.notification_slack_http import ProviderFailure
    config = world.config(channel)
    row, code = world.challenge(config)
    from apps.integrations.notification_proofs import consume
    endpoint = consume(config, EndpointProof(code, "private-id", config.integration_identity, "subject", private=True))
    provider = provider_for(config)
    monkeypatch.setattr(provider, "send_personal", Mock(side_effect=ProviderFailure("invalid_endpoint")))
    result = provider.send(SimpleNamespace(pk=1, endpoint=endpoint), {"text": "Update"})
    assert not result.accepted and result.error_code == "invalid_endpoint"
    endpoint.refresh_from_db()
    assert endpoint.revoked_at is None and endpoint.verification_state == "verified"


def test_rejected_oauth_proof_keeps_its_attempt_budget(world, monkeypatch):
    config = world.config("discord")
    row, code = world.challenge(config)
    def invalid(*args, **kwargs):
        return CallbackEvent(proof=EndpointProof(code, "private-id", config.integration_identity, "subject", private=False))
    monkeypatch.setattr("apps.integrations.notification_discord.DiscordProvider.oauth_proof", invalid)
    response = world.client(world.owner).post(verify_url(world, row), {"code": "code", "state": state_for(row, code)}, format="json")
    assert response.status_code == 400
    row.refresh_from_db()
    assert row.attempts == 1 and row.consumed_at is None


@pytest.mark.parametrize("channel", CHANNELS)
def test_providers_authorize_to_frontend_with_exact_registered_redirect(world, channel, settings, monkeypatch):
    from apps.integrations.notification_providers import provider_for
    from apps.integrations.notification_slack import workspace_identity
    identities = {"slack": workspace_identity("T123"), "mattermost": "https://chat.example.test", "discord": "123:456"}
    config = world.config(channel, integration_identity=identities[channel])
    config.set_credentials({"client_id": "client", "client_secret": "secret", "bot_token": "bot",
        "team_id": "T123", "server_url": identities["mattermost"], "application_id": "123", "guild_id": "456"})
    config.save(update_fields=["credentials"])
    monkeypatch.setattr("apps.integrations.notification_mattermost.resolve_server", lambda *_: None)
    uri = f"https://app.example.test/m/{world.space.pk}/member/inbox?section=channels"
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", uri)
    row, code = world.challenge(config)
    params = parse_qs(urlsplit(provider_for(config).start_challenge(row, code)["connect_url"]).query)
    assert params["redirect_uri"] == [uri]
    assert read_state(config, params["state"][0], user_id=world.owner.pk, challenge_id=row.pk)[0].pk == row.pk
