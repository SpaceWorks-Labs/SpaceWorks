import hashlib
import hmac
import json
import time
from unittest.mock import Mock

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.claim_routes import CLAIM_REACHABLE_PREFIXES
from apps.apiclients.scope_registry import _protected_prefixes
from apps.integrations.notification_slack_views import ChatInboundView, SlackInstallStartView, ChatOAuthCallbackView
from apps.integrations.notification_mattermost_urls import MattermostInstallationView
from apps.integrations.notification_discord_urls import DiscordInstallationView
from tests.accounts.reauth_helpers import reauthenticate

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("channel", ["slack", "mattermost", "discord"])
def test_new_routes_are_outside_hmac_and_claim_surfaces(channel):
    prefix = f"/api/v1/integrations/makerspace/1/{channel}/"
    for suffix in ("oauth/callback", "inbound", "install/start" if channel == "slack" else "installation"):
        path = prefix + suffix
        assert resolve(path).url_name.startswith(f"notification-{channel}-")
        assert not path.startswith(CLAIM_REACHABLE_PREFIXES)
        assert not path.lstrip("/").startswith(_protected_prefixes())
    # Adding registry entries for these excluded routes would be stale by construction.


def test_signed_slack_url_challenge_and_interactivity_acknowledge(chat):
    c = chat("slack")
    body = json.dumps({"type": "url_verification", "challenge": "provider-challenge"}).encode()
    timestamp = str(int(time.time()))
    signature = "v0=" + hmac.new(b"signing-secret", b"v0:" + timestamp.encode() + b":" + body,
                                 hashlib.sha256).hexdigest()
    request = APIRequestFactory().post("/inbound", body, content_type="application/json",
        HTTP_X_SLACK_REQUEST_TIMESTAMP=timestamp, HTTP_X_SLACK_SIGNATURE=signature)
    response = ChatInboundView.as_view(channel="slack")(request, makerspace_id=c.space.pk)
    assert response.status_code == 200 and response.data == {"challenge": "provider-challenge"}
    c.endpoint.refresh_from_db()
    assert c.endpoint.last_inbound_at is None


def test_install_start_returns_pkce_url_without_credentials(chat):
    c = chat("slack")
    request = APIRequestFactory().post("/install/start")
    force_authenticate(request, user=c.user)
    response = SlackInstallStartView.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 201
    assert "code_challenge=" in response.data["connect_url"]
    assert "private-bot-token" not in response.data["connect_url"] and "secret=" not in response.data["connect_url"]
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("channel", ["mattermost", "discord"])
def test_installation_rejects_unknown_or_browser_destination_fields(chat, channel):
    c = chat(channel)
    request = APIRequestFactory().post("/installation", {"destination": "someone-else", "bot_token": "secret"}, format="json")
    force_authenticate(request, user=c.user, token=reauthenticate(None, c.user))
    view = MattermostInstallationView if channel == "mattermost" else DiscordInstallationView
    response = view.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 400


def test_oauth_head_never_exchanges_code(chat, monkeypatch):
    c = chat("discord")
    exchange = Mock(side_effect=AssertionError("HEAD must not consume OAuth"))
    monkeypatch.setattr("apps.integrations.notification_discord.api", exchange)
    request = APIRequestFactory().head("/oauth/callback?state=anything&code=anything")
    response = ChatOAuthCallbackView.as_view(channel="discord")(request, makerspace_id=c.space.pk)
    assert response.status_code == 401
    request = APIRequestFactory().head("/oauth/callback?state=anything&code=anything")
    force_authenticate(request, user=c.user)
    response = ChatOAuthCallbackView.as_view(channel="discord")(request, makerspace_id=c.space.pk)
    assert response.status_code == 405
    exchange.assert_not_called()


def test_redirect_uri_is_the_fixed_registered_value(settings):
    # Providers match redirect URIs byte for byte; per-connection bindings live in the signed state.
    from rest_framework.exceptions import ValidationError
    from apps.integrations.notification_slack_oauth import redirect_uri
    settings.NOTIFICATION_SLACK_REDIRECT_URI = "https://app.example/member/notifications"
    assert redirect_uri("slack", 42) == "https://app.example/member/notifications"
    settings.NOTIFICATION_SLACK_REDIRECT_URI = "https://api.example/makerspace/{makerspace_id}/slack/oauth/callback"
    with pytest.raises(ValidationError):
        redirect_uri("slack", 42)
