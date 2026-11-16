from urllib.parse import parse_qs, urlsplit

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_proofs import consume
from apps.integrations.notification_providers import EndpointProof, provider_for
from apps.integrations.notification_slack import workspace_identity
from apps.integrations.notification_slack_oauth import read_state, redirect_uri

pytestmark = pytest.mark.django_db
CHANNELS = ["slack", "mattermost", "discord"]


def installed(world, channel):
    identity = {"slack": workspace_identity("T123"), "mattermost": "https://chat.example.test",
                "discord": "123:456"}[channel]
    config = world.config(channel, integration_identity=identity)
    config.set_credentials({"client_id": "client", "client_secret": "secret", "bot_token": "bot",
        "team_id": "T123", "server_url": "https://chat.example.test", "application_id": "123", "guild_id": "456"})
    config.save(update_fields=["credentials"])
    return config


@pytest.mark.parametrize("channel", CHANNELS)
def test_registered_redirect_is_exact_for_authorization_and_exchange(world, settings, monkeypatch, channel):
    uri = "https://app.example.test/member/inbox?section=channels&fixed=%2f"
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", uri)
    config = installed(world, channel)
    row, code = world.challenge(config)
    monkeypatch.setattr("apps.integrations.notification_mattermost.resolve_server", lambda *_: None)
    provider = provider_for(config)
    result = provider.start_challenge(row, code)
    query = parse_qs(urlsplit(result["connect_url"]).query)
    assert query["redirect_uri"] == [uri]
    assert read_state(config, query["state"][0], user_id=world.owner.pk, challenge_id=row.pk)[0].pk == row.pk
    calls = []
    def stop(*args, **kwargs):
        calls.append(kwargs["data"])
        raise RuntimeError("Token exchange inspected without network I/O")
    monkeypatch.setattr(f"apps.integrations.notification_{channel}.{'mattermost_api' if channel == 'mattermost' else 'api'}", stop)
    with pytest.raises(RuntimeError):
        provider.oauth_proof({"state": query["state"][0], "code": "provider-code"}, world.owner.pk)
    assert calls[0]["redirect_uri"] == uri
    assert redirect_uri(channel, 99, 999) == uri


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("uri", ["https://app.example.test/{challenge_id}", "https://app.example.test/{makerspace_id}",
                                    "http://app.example.test/inbox", "https://app.example.test/inbox#fragment"])
def test_dynamic_and_invalid_registered_redirects_fail_closed(settings, channel, uri):
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", uri)
    with pytest.raises(ValidationError):
        redirect_uri(channel, 1, 2)


@pytest.mark.parametrize("channel", CHANNELS)
def test_start_returns_state_bound_challenge_without_changing_redirect(world, settings, monkeypatch, channel):
    world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"notifications", channel})
    world.space.save(update_fields=["enabled_modules"])
    config = installed(world, channel)
    uri = "https://app.example.test/member/inbox?section=channels"
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", uri)
    monkeypatch.setattr("apps.integrations.notification_mattermost.resolve_server", lambda *_: None)
    response = world.client(world.owner).post(f"/api/v1/integrations/makerspace/{world.space.pk}/personal/endpoints/start",
        {"channel": channel, "consent": True, "consent_version": "v1"}, format="json")
    assert response.status_code == 201, response.data
    data = response.data
    query = parse_qs(urlsplit(data["connect_url"]).query)
    assert data["oauth_state"] == query["state"][0]
    assert query["redirect_uri"] == [uri]
    assert read_state(config, data["oauth_state"], user_id=world.owner.pk,
                      challenge_id=data["challenge_id"])[0].pk == data["challenge_id"]


@pytest.mark.parametrize("change", ["generation", "identity", "provider", "revocation", "verification", "disabled"])
def test_api_reports_effective_endpoint_validity_and_allows_reconnect(world, change):
    config = world.config()
    row, code = world.challenge(config)
    endpoint = consume(config, EndpointProof(code, "private", config.integration_identity, "subject", private=True))
    url = f"/api/v1/integrations/makerspace/{world.space.pk}/personal/endpoints"
    api = world.client(world.owner)
    assert api.get(url).data["results"][0]["effective_valid"] is True
    if change == "generation":
        config.generation += 1
    elif change == "identity":
        config.integration_identity = "another-installation"
    elif change == "provider":
        config.provider = "other"
    elif change == "disabled":
        config.personal_enabled = False
    elif change == "revocation":
        endpoint.revoked_at = timezone.now()
    else:
        endpoint.verification_state = "revoked"
    endpoint.save()
    config.save()
    data = api.get(url).data["results"][0]
    assert data["effective_valid"] is False
    assert "destination" not in data and "provider_subject" not in data
    if change == "generation":
        fresh, proof = world.challenge(config)
        replacement = consume(config, EndpointProof(proof, "private", config.integration_identity, "subject", private=True))
        endpoint.refresh_from_db()
        assert endpoint.revoked_at and replacement.pk != endpoint.pk
        assert NotificationEndpoint.objects.filter(configuration=config, revoked_at=None).count() == 1
