from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.integrations.notification_proofs import consume, verified_callback
from apps.integrations.notification_oauth_verification import verify_oauth
from apps.integrations.notification_slack import complete_install, install_url, workspace_identity
from apps.integrations.notification_slack_oauth import (
    state_for, read_state, verifier, pkce, install_challenge, redirect_uri,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("channel", ["slack", "mattermost", "discord"])
@pytest.mark.parametrize("failure", ["wrong_user", "wrong_config", "wrong_tenant", "expired", "generation", "identity", "purpose", "tampered"])
def test_state_cannot_cross_account_installation_or_expiry(chat, channel, failure):
    c = chat(channel)
    row, code = c.challenge()
    state = state_for(row, code)
    assert len(state) <= 512
    kwargs = {}
    if failure == "wrong_user":
        kwargs["user_id"] = c.user.pk + 1
    elif failure == "wrong_config":
        c.config.pk += 999
    elif failure == "wrong_tenant":
        c.config.makerspace_id += 999
    elif failure == "expired":
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save(update_fields=["expires_at"])
    elif failure == "generation":
        c.config.generation += 1
    elif failure == "identity":
        c.config.integration_identity = "other-installation"
    elif failure == "purpose":
        kwargs["purpose"] = "install"
    else:
        state += "modified"
    with pytest.raises(ValidationError):
        read_state(c.config, state, **kwargs)


@pytest.mark.parametrize("channel", ["slack", "mattermost", "discord"])
def test_proven_endpoint_consumes_state_once(chat, channel):
    from apps.integrations.notification_providers import EndpointProof
    c = chat(channel)
    row, code = c.challenge()
    state = state_for(row, code)
    assert read_state(c.config, state)[0].pk == row.pk
    endpoint = consume(c.config, EndpointProof(code, "proven-private-id", c.config.integration_identity,
                                              "proven-subject", private=True))
    assert endpoint.user_id == c.user.pk and endpoint.makerspace_id == c.space.pk
    with pytest.raises(ValidationError):
        read_state(c.config, state)


def slack_oidc(c, monkeypatch, *, team="T123", nonce=None, bad_signature=False):
    row, code = c.challenge()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token_key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if bad_signature else key
    claims = {"iss": "https://slack.com", "aud": "app-id", "sub": "U123", "exp": int(timezone.now().timestamp()) + 300,
        "iat": int(timezone.now().timestamp()), "nonce": nonce or verifier(code),
        "https://slack.com/team_id": team, "https://slack.com/user_id": "U123"}
    token = jwt.encode(claims, token_key, algorithm="RS256", headers={"kid": "key"})
    import json
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "key"
    fake = Mock(side_effect=[{"id_token": token, "access_token": "ephemeral-user-token"}, {"keys": [jwk]}])
    monkeypatch.setattr("apps.integrations.notification_slack.api", fake)
    monkeypatch.setattr("apps.integrations.notification_slack.slack_api", Mock(return_value={
        "sub": "U123", "https://slack.com/team_id": team, "https://slack.com/user_id": "U123"}))
    request = SimpleNamespace(method="POST", path=f"/personal/challenges/{row.pk}/verify",
        user=c.user, challenge=row,
        data={"state": state_for(row, code), "code": "provider-authorization-code"})
    return request, fake


def test_slack_oidc_signature_nonce_and_team_produce_proof(chat, monkeypatch):
    c = chat("slack")
    request, fake = slack_oidc(c, monkeypatch)
    endpoint = verify_oauth(request.challenge, request)
    assert endpoint.destination == "U123"
    assert endpoint.provider_subject == "T123:U123"
    assert fake.call_args_list[0].kwargs["data"]["redirect_uri"] == redirect_uri("slack", c.space.pk, request.challenge.pk)
    with pytest.raises(ValidationError):
        verify_oauth(request.challenge, request)
    assert fake.call_count == 2  # Replay rejected before token I/O.


@pytest.mark.parametrize("failure", ["team", "nonce", "signature"])
def test_slack_oidc_rejects_wrong_workspace_nonce_or_signature(chat, monkeypatch, failure):
    c = chat("slack")
    request, _ = slack_oidc(c, monkeypatch, team="TOTHER" if failure == "team" else "T123",
        nonce="wrong-nonce" if failure == "nonce" else None, bad_signature=failure == "signature")
    with pytest.raises(ValidationError):
        verify_oauth(request.challenge, request)


@pytest.mark.parametrize("channel", ["mattermost", "discord"])
def test_oauth_identity_is_fetched_from_provider_never_browser_ids(chat, channel, monkeypatch):
    c = chat(channel)
    row, code = c.challenge()
    tokens = {"access_token": "ephemeral-user-token", "scope": "identify"}
    fake = Mock(side_effect=[tokens, {"id": c.endpoint.destination}])
    target = "mattermost_api" if channel == "mattermost" else "api"
    monkeypatch.setattr(f"apps.integrations.notification_{channel}.{target}", fake)
    request = SimpleNamespace(method="POST", path=f"/personal/challenges/{row.pk}/verify", user=c.user,
        data={"state": state_for(row, code), "code": "provider-code", "user_id": "attacker-id"})
    endpoint = verify_oauth(row, request)
    assert endpoint.destination == c.endpoint.destination
    token_data = fake.call_args_list[0].kwargs["data"]
    if channel == "mattermost":
        assert token_data["code_verifier"] == verifier(code)
    assert token_data["redirect_uri"] == redirect_uri(channel, c.space.pk, row.pk)
    with pytest.raises(ValidationError):
        verify_oauth(row, request)
    assert fake.call_count == 2


def test_slack_install_state_is_single_use_and_reinstall_advances_generation(chat, monkeypatch):
    c = chat("slack")
    challenge, code = install_challenge(c.user, c.config)
    params = parse_qs(urlsplit(install_url(c.config, challenge, code)).query)
    assert params["code_challenge"] == [pkce(code)]
    fake = Mock(return_value={"ok": True, "access_token": "new-bot-token", "team": {"id": "TNEW"}})
    monkeypatch.setattr("apps.integrations.notification_slack.api", fake)
    row = complete_install(c.config, {"state": params["state"][0], "code": "installation-code"})
    assert row.generation == c.config.generation + 1 and row.integration_identity == workspace_identity("TNEW")
    assert row.get_credentials()["team_id"] == "TNEW"
    assert "new-bot-token" not in row.credentials
    assert "client_secret" not in fake.call_args.kwargs["data"]  # Slack's PKCE exchange.
    with pytest.raises(ValidationError):
        complete_install(c.config, {"state": params["state"][0], "code": "second-code"})
    fake.assert_called_once()


@pytest.mark.parametrize("channel", ["slack", "mattermost", "discord"])
def test_redirect_uri_is_required_server_setting(chat, channel, settings):
    c = chat(channel)
    setattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", "http://untrusted.example/callback")
    with pytest.raises(ValidationError):
        redirect_uri(channel)
