"""Real lock contention must serialize sign-in with departure and refresh."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.account_deletion_credentials import revoke
from apps.accounts.account_restore import identifier_fingerprint, restore_locked
from apps.accounts.attestation import VerifiedAttestation, challenge_digest
from apps.accounts.models import User
from apps.accounts.models_devices import DeviceAttestationChallenge, DeviceGrant
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.services_device_grants import issue_first_device_session
from apps.accounts.services_device_tokens import issue_device_token_pair, rotate_device_refresh
from apps.accounts.services_phone import _digest, confirm_login_challenge
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.native_helpers_m1d import configure_apple, mock_attestation
from tests.accounts.mobile_integration_helpers import PREFIX
from tests.accounts.test_account_deletion_refresh_races import _wait_until_blocked
from tests.accounts.test_social_first_grant import issue_challenge

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "Original login password 123!"
NUMBER = "+14155552671"


def waiting_worker(pool, operation):
    ready, pids = Event(), []

    def run():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '8s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.append(cursor.fetchone()[0])
            ready.set()
            return operation()
        finally:
            close_old_connections()

    future = pool.submit(run)
    assert ready.wait(timeout=5)
    _wait_until_blocked(pids[0], future)
    return future


def bounded_lock_wait():
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '2s'")


@pytest.mark.parametrize("change", ["departure", "restore", "password"])
def test_browser_login_rechecks_authenticated_snapshot_after_waiting_for_user(change):
    user = User.objects.create_user(username="browser-issuance-race", password=PASSWORD)

    def login():
        try:
            SpaceWorksRefreshToken.for_user(user)
        except AuthenticationFailed:
            return "refused"
        return "issued"

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = waiting_worker(pool, login)
            bounded_lock_wait()
            revoke(locked, timezone.now())
            if change == "password":
                locked.set_password("Replacement login password 456!")
                locked.save(update_fields=["password"])
            else:
                locked.is_active = False
                locked.set_unusable_password()
                locked.deletion_requested_at = timezone.now()
                locked.deletion_purge_after = timezone.now() + timedelta(days=90)
                locked.save(update_fields=["password", "is_active", "deletion_requested_at",
                                           "deletion_purge_after"])
                if change == "restore":
                    restore_locked(locked, fingerprint=identifier_fingerprint(locked),
                                   new_password="Recovered login password 789!")
        assert future.result(timeout=10) == "refused"
    assert not OutstandingToken.objects.filter(user=user).exists()
    if change != "departure":
        # Fresh authentication still works after a credential change/restore.
        current = User.objects.get(pk=user.pk)
        assert SpaceWorksRefreshToken.for_user(current)["sid"]


@pytest.mark.parametrize("issuer", ["password", "phone", "social", "mfa"])
def test_native_signin_waits_for_user_without_holding_refresh_registration(
    issuer, settings, monkeypatch,
):
    registration = configure_apple(settings)
    user = User.objects.create_user(username="native-issuance-race", password=PASSWORD)
    grant = DeviceGrant.objects.create(user=user, registration=registration, platform="apple",
        app_id=registration.app_id, environment=registration.environment,
        signing_identity=PREFIX, attested_at=timezone.now(), last_used_at=timezone.now())
    _, refresh, _ = issue_device_token_pair(user, grant)
    raw = issue_challenge(APIClient())
    challenge = DeviceAttestationChallenge.objects.get(challenge_digest=challenge_digest(raw))
    verified = VerifiedAttestation("device-subject", {"signing_identity": PREFIX})
    mock_attestation(monkeypatch, raw)

    def signin():
        if issuer == "password":
            result = APIClient().post("/api/v1/auth/device/login", {
                "username": user.username, "password": PASSWORD, "platform": "apple",
                "app_id": registration.app_id, "environment": registration.environment,
                "challenge": raw, "attestation": {"assertion": "opaque"},
            }, format="json")
            assert result.status_code == 200
        elif issuer == "social":
            from types import SimpleNamespace
            from apps.accounts.services_social_login import issue_social_session
            issue_social_session(user, surface="member", delivery="device",
                nonce_row=SimpleNamespace(device_grant=None, device_grant_id=None,
                                          attestation_challenge=challenge),
                verified_attestation=verified)
        elif issuer == "mfa":
            from apps.accounts.mfa_sessions import device_context, issue_session
            with transaction.atomic():
                issue_session(user, {"surface": "member", "kind": "person",  # #63: token kind is "person"
                                     "credential_generation": user.credential_generation, "device": device_context(
                    challenge, verified, login_method="password")}, APIRequestFactory().post("/"))
        else:
            issue_first_device_session(user, challenge, verified, login_method="phone")
        return "issued"

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = waiting_worker(pool, signin)
            bounded_lock_wait()
            # Old issuers held registration while waiting for User. Refresh's
            # joined credential lock then deadlocked on that same registration.
            assert rotate_device_refresh(refresh)[0]
        assert future.result(timeout=10) == "issued"
    assert DeviceGrant.objects.filter(user=user, status="active").count() == 2


@pytest.mark.parametrize("delivery", ["web", "device"])
def test_phone_login_waits_for_user_without_holding_departures_challenge(delivery, settings):
    user = User.objects.create_user(username="phone-issuance-race", password=PASSWORD,
                                    phone_e164=NUMBER)
    User.objects.filter(pk=user.pk).update(phone_verified_at=timezone.now())
    challenge = None
    if delivery == "device":
        registration = configure_apple(settings)
        from tests.accounts.test_social_first_grant import create_challenge
        challenge = create_challenge(registration, "phone-race-attestation")
    otp = PhoneVerificationChallenge.objects.create(user=user, purpose="login",
        phone_e164=NUMBER, code_digest=_digest("123456", NUMBER),
        attestation_challenge=challenge, expires_at=timezone.now() + timedelta(minutes=5),
        last_sent_at=timezone.now())

    def confirm():
        try:
            confirm_login_challenge(NUMBER, "123456", delivery=delivery)
        except ValidationError:
            return "refused"
        return "authenticated"

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = waiting_worker(pool, confirm)
            bounded_lock_wait()
            # Must not wait for a challenge held by the blocked confirmation.
            revoke(locked, timezone.now())
            locked.is_active = False
            locked.deletion_requested_at = timezone.now()
            locked.save(update_fields=["is_active", "deletion_requested_at"])
        assert future.result(timeout=10) == "refused"
    otp.refresh_from_db()
    assert otp.consumed_at is not None and otp.failed_attempts == 0
