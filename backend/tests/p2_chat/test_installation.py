from unittest.mock import Mock

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.integrations.notification_discord_urls import DiscordInstallationView
from apps.integrations.notification_mattermost_urls import MattermostInstallationView
from apps.integrations.notification_slack_views import SlackInstallStartView
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.reauth_helpers import reauthenticate
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def test_discord_registration_verifies_app_public_key_and_guild_before_rotation(chat, monkeypatch):
    c = chat("discord")
    fake = Mock(side_effect=[{"id": "123", "verify_key": "00" * 32}, {"id": "456"}])
    monkeypatch.setattr("apps.integrations.notification_slack_installation.api", fake)
    request = APIRequestFactory().post("/installation", {key: c.creds[key] for key in
        ("bot_token", "application_id", "public_key", "guild_id", "client_secret")}, format="json")
    # Installation bodies carry bot secrets: the session must have stepped up.
    force_authenticate(request, user=c.user, token=reauthenticate(None, c.user))
    response = DiscordInstallationView.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 200
    c.config.refresh_from_db()
    assert c.config.generation == 2
    assert c.config.integration_identity == "123:456"
    assert "private-bot-token" not in c.config.credentials
    assert "private-bot-token" not in str(response.data)


def test_discord_registration_cannot_install_another_app_or_guild(chat, monkeypatch):
    c = chat("discord")
    monkeypatch.setattr("apps.integrations.notification_slack_installation.api",
        Mock(return_value={"id": "other-application", "verify_key": "00" * 32}))
    request = APIRequestFactory().post("/installation", {key: c.creds[key] for key in
        ("bot_token", "application_id", "public_key", "guild_id", "client_secret")}, format="json")
    # Installation bodies carry bot secrets: the session must have stepped up.
    force_authenticate(request, user=c.user, token=reauthenticate(None, c.user))
    response = DiscordInstallationView.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 400
    c.config.refresh_from_db()
    assert c.config.generation == 1


def test_mattermost_registration_requires_bot_and_rotates_encrypted_credentials(chat, monkeypatch):
    c = chat("mattermost")
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.resolve_server", Mock())
    fake = Mock(return_value={"id": "b" * 26, "is_bot": True, "delete_at": 0})
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.mattermost_api", fake)
    data = {key: c.creds[key] for key in ("server_url", "bot_token", "client_secret", "webhook_token")}
    data["client_id"] = "a" * 26
    request = APIRequestFactory().post("/installation", data, format="json")
    # Installation bodies carry bot secrets: the session must have stepped up.
    force_authenticate(request, user=c.user, token=reauthenticate(None, c.user))
    response = MattermostInstallationView.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 200
    c.config.refresh_from_db()
    assert c.config.generation == 2 and "private-bot-token" not in c.config.credentials
    assert "bot_token" not in response.data


@pytest.mark.parametrize("kind", ["member", "foreign_manager"])
def test_channel_installation_remains_space_manager_only(chat, kind):
    c = chat("slack")
    if kind == "member":
        actor = make_member("p2-ordinary-member", c.space,
            membership_role=MakerspaceMembership.Role.CUSTOM, role=User.Role.REQUESTER)
        membership = actor.makerspace_memberships.get(makerspace=c.space)
        membership.assigned_role = c.space.roles.get(slug="member")
        membership.save(update_fields=["assigned_role"])
    else:
        actor = make_member("p2-foreign-manager", make_space("p2-foreign-space"))
    request = APIRequestFactory().post("/install/start")
    force_authenticate(request, user=actor)
    response = SlackInstallStartView.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 403


@pytest.mark.parametrize("channel", ["mattermost", "discord"])
def test_installation_secrets_require_a_recent_step_up(chat, channel, monkeypatch):
    from tests.accounts.reauth_helpers import session_token
    c = chat(channel)
    provider = Mock(side_effect=AssertionError("no provider call before step-up"))
    monkeypatch.setattr("apps.integrations.notification_slack_installation.api", provider)
    monkeypatch.setattr("apps.integrations.notification_mattermost_http.mattermost_api", provider)
    request = APIRequestFactory().post("/installation", {key: c.creds[key] for key in
        ("bot_token", "client_secret")}, format="json")
    force_authenticate(request, user=c.user, token=session_token(c.user))
    view = MattermostInstallationView if channel == "mattermost" else DiscordInstallationView
    response = view.as_view()(request, makerspace_id=c.space.pk)
    assert response.status_code == 403 and response.data["code"] == "recent_reauth_required"
    c.config.refresh_from_db()
    assert c.config.generation == 1
    provider.assert_not_called()
