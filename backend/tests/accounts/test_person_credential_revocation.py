"""Review fix: account-wide revocation and purge reach #196 person bearers (PATs, OAuth)."""
from datetime import timedelta

import pytest
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model, get_grant_model, \
    get_refresh_token_model

from apps.accounts.account_purge import _global_rows
from apps.accounts.credential_revocation import revoke_all_credentials, revoke_sessions_only
from apps.accounts.models import User
from apps.apiclients.models_tokens import OAuthConsent, PersonalAccessToken
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db


def _bearers(user):
    pat, _ = PersonalAccessToken.issue(user=user, name="Sync", scopes=["account:read"], makerspace=None,
                                       days=30, mfa_claims={})
    app = get_application_model().objects.create(
        name="App", client_type="public", authorization_grant_type="authorization-code",
        redirect_uris="https://app.example/cb",
    )
    OAuthConsent.objects.create(user=user, application=app, scopes=["account:read"])
    expires = timezone.now() + timedelta(hours=1)
    access = get_access_token_model().objects.create(user=user, application=app, token="swoa_a",
                                                     expires=expires, scope="account:read")
    get_refresh_token_model().objects.create(user=user, application=app, token="swoa_r", access_token=access)
    get_grant_model().objects.create(user=user, application=app, code="c", expires=expires,
                                     redirect_uri="https://app.example/cb", scope="account:read")
    return pat


def _oauth_rows(user):
    return sum(model().objects.filter(user=user).count()
               for model in (get_access_token_model, get_refresh_token_model, get_grant_model))


@pytest.mark.parametrize("revoke", [revoke_all_credentials, revoke_sessions_only])
def test_account_revocation_ends_personal_tokens_and_app_connections(revoke):
    user = make_user("rev-pat", access_status=User.AccessStatus.ACTIVE)
    pat = _bearers(user)
    counts = revoke(user, reason="compromise")
    pat.refresh_from_db()
    assert pat.revoked_at is not None and not pat.active
    assert not OAuthConsent.objects.filter(user=user).exists()
    assert _oauth_rows(user) == 0
    assert counts["personal_access_tokens"] == 1 and counts["oauth_consents"] == 1
    # Idempotent: a repeat call revokes nothing new.
    assert revoke(user, reason="again")["personal_access_tokens"] == 0


def test_purge_global_rows_delete_person_bearers():
    user = make_user("purge-pat", access_status=User.AccessStatus.ACTIVE)
    _bearers(user)
    _global_rows(user)
    assert not PersonalAccessToken.objects.filter(user=user).exists()
    assert not OAuthConsent.objects.filter(user=user).exists()
    assert _oauth_rows(user) == 0
