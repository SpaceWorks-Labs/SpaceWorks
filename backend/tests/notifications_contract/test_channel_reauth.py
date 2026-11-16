"""Channel credential writes require a recent session-bound step-up; toggles do not."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication import WINDOW
from apps.integrations.models_endpoints import ChannelConfiguration
from tests.accounts.reauth_helpers import reauthenticate, session_token
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def url(contract):
    return f"/api/v1/integrations/makerspace/{contract.space.pk}/channels/telegram"


def session_client(user):
    api = APIClient()
    api.force_authenticate(user=user, token=session_token(user))
    return api


def unchanged(contract):
    row = ChannelConfiguration.objects.get(pk=contract.config.pk)
    return row.generation == contract.config.generation and row.credentials == contract.config.credentials


@pytest.mark.parametrize("credentials", [{"bot_token": "stolen-session-token"}, {}], ids=["write", "clear"])
def test_stale_session_cannot_write_or_clear_a_credential(contract, credentials):
    manager = make_member("reauth-stale-manager", contract.space)
    response = session_client(manager).patch(url(contract), {"credentials": credentials}, format="json")
    assert response.status_code == 403 and response.data["code"] == "recent_reauth_required"
    assert unchanged(contract)


def test_expired_step_up_is_refused_and_a_fresh_one_admits(contract):
    manager = make_member("reauth-expired-manager", contract.space)
    api = APIClient()
    token = reauthenticate(api, manager)
    ReauthenticationSession.objects.filter(session_id=token["sid"]).update(
        auth_time=timezone.now() - WINDOW - timedelta(seconds=1))
    response = api.patch(url(contract), {"credentials": {"bot_token": "late-token"}}, format="json")
    assert response.status_code == 403 and response.data["code"] == "recent_reauth_required"
    assert unchanged(contract)
    reauthenticate(api, manager)
    response = api.patch(url(contract), {"credentials": {"bot_token": "fresh-token"}}, format="json")
    assert response.status_code == 200 and response.data["generation"] == contract.config.generation + 1


def test_a_proof_does_not_transfer_to_another_session(contract):
    manager = make_member("reauth-other-session-manager", contract.space)
    reauthenticate(APIClient(), manager)
    response = session_client(manager).patch(url(contract), {"credentials": {"bot_token": "x"}}, format="json")
    assert response.status_code == 403 and response.data["code"] == "recent_reauth_required"
    assert unchanged(contract)


def test_non_secret_settings_edits_need_no_step_up(contract):
    manager = make_member("reauth-toggle-manager", contract.space)
    response = session_client(manager).patch(url(contract), {"email_fallback": True}, format="json")
    assert response.status_code == 200 and response.data["generation"] == contract.config.generation
    assert ChannelConfiguration.objects.get(pk=contract.config.pk).email_fallback is True
