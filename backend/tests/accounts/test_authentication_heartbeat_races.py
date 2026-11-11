"""A native heartbeat never holds Grant while waiting for credential revocation."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import transaction
from django.urls import resolve
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.accounts.credential_revocation import revoke_account_sessions, revoke_sessions_only
from apps.accounts.models import User
from apps.accounts.models_devices import DeviceGrant, DeviceRefreshFamily
from tests.accounts.account_factories import make_staff
from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login
from tests.accounts.test_account_issuance_races import bounded_lock_wait, waiting_worker
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db(transaction=True)


def session(kind, settings, monkeypatch):
    if kind == "staff":
        user = make_staff(make_space("heartbeat-race"), username="heartbeat-race",
                          password="strong-device-password")
        login = attested_staff_login
    else:
        user = User.objects.create_user(username="heartbeat-race", password="strong-device-password")
        login = attested_login
    response, _ = login(APIClient(), user, settings, monkeypatch)
    assert response.status_code == 200
    return user, response.data["access"], DeviceGrant.objects.get(user=user)


def authenticate(access):
    raw = APIRequestFactory().get("/api/v1/auth/me", HTTP_AUTHORIZATION=f"Bearer {access}")
    raw.resolver_match = resolve(raw.path)
    return SpaceWorksJWTAuthentication().authenticate(Request(raw))


@pytest.mark.parametrize("kind", ["member", "staff"])
@pytest.mark.parametrize("change", ["logout_all", "password", "grant", "family", "registration"])
def test_heartbeat_waits_for_user_then_rechecks_revocation(kind, change, settings, monkeypatch):
    user, access, grant = session(kind, settings, monkeypatch)
    before = grant.last_used_at

    def heartbeat():
        try:
            authenticate(access)
        except AuthenticationFailed:
            return "refused"
        return "authenticated"

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = waiting_worker(pool, heartbeat)
            bounded_lock_wait()
            # With Grant -> User the worker already owns this row; this lock
            # times out rather than letting logout/password reset complete.
            DeviceGrant.objects.select_for_update().get(pk=grant.pk)
            if change == "logout_all":
                revoke_account_sessions(user)
            elif change == "password":
                revoke_sessions_only(user, reason="password_change", actor=user)
                user.set_password("Replacement-password-936!")
                user.save(update_fields=["password"])
            elif change == "grant":
                DeviceGrant.objects.filter(pk=grant.pk).update(status="revoked", revoked_at=timezone.now())
            elif change == "family":
                DeviceRefreshFamily.objects.filter(grant=grant).update(revoked_at=timezone.now())
            else:
                type(grant.registration).objects.filter(pk=grant.registration_id).update(status="revoked")
        assert future.result(timeout=10) == "refused"
    grant.refresh_from_db()
    assert grant.last_used_at == before


def test_heartbeat_refuses_member_deleted_while_waiting(settings, monkeypatch):
    from apps.accounts.account_deletion_credentials import revoke

    user, access, grant = session("member", settings, monkeypatch)

    def heartbeat():
        with pytest.raises(AuthenticationFailed):
            authenticate(access)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = waiting_worker(pool, heartbeat)
            bounded_lock_wait()
            revoke(user, timezone.now())
            user.is_active = False
            user.deletion_requested_at = timezone.now()
            user.save(update_fields=["is_active", "deletion_requested_at"])
        future.result(timeout=10)
    grant.refresh_from_db()
    assert grant.status == "revoked"


@pytest.mark.parametrize("kind", ["member", "staff"])
def test_live_heartbeat_updates_usage_and_preserves_native_context(kind, settings, monkeypatch):
    user, access, grant = session(kind, settings, monkeypatch)
    before = grant.last_used_at
    actor, token = authenticate(access)
    grant.refresh_from_db()
    assert actor.pk == user.pk and actor.native_device_session
    assert token["device_grant_id"] == str(grant.pk)
    assert grant.last_used_at > before
