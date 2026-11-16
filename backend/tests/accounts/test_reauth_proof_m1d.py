"""Fresh proof is committed independently of a failed account-deletion attempt."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from apps.accounts import account_deletion as deletion, reauthentication as auth
from apps.accounts import reauthentication_intents as intents, reauthentication_factors as factors
from apps.accounts import reauthentication_phone as phone
from apps.accounts.mfa_crypto import totp
from apps.accounts.models_devices import DeviceRefreshFamily
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.models_social import SocialIdentity
from apps.audit.models import AuditLog
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.accounts.native_helpers_m1d import attested_login
from tests.accounts.test_reauthentication import ORIGIN, PASSWORD, request
from tests.accounts.test_support_m1d import account, m1d_config, proven

pytestmark = pytest.mark.django_db
DELETE = "/api/v1/auth/account/deletion"


@pytest.mark.parametrize("method", ["password", "password_totp", "passwordless_totp"])
def test_real_verify_endpoint_proves_deletion_and_mfa_replays_fail(method):
    user = account(password=None if method == "passwordless_totp" else PASSWORD)
    req = request(user, surface="member")
    client = APIClient()
    client.force_authenticate(user, token=req.auth)
    assert client.post(DELETE, {"confirm": "DELETE"}, format="json").status_code == 403
    values = {"password": PASSWORD} if method != "passwordless_totp" else {}
    if method != "password":
        row, secret = enrolled(user)
        values["code"] = totp(secret, int(timezone.now().timestamp() // 30))
    response = client.post("/api/v1/auth/reauth", values, format="json", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 200 and response.data["verified"]
    if method != "password":
        with pytest.raises(AuthenticationFailed):
            auth.verify(request(user), **values)
        row.refresh_from_db()
        assert row.last_step >= 0
    response = client.post(DELETE, {"confirm": "DELETE"}, format="json")
    assert response.status_code == 202
    assert response.cookies["refresh_token"]["max-age"] == 0
    user.refresh_from_db()
    assert not user.is_active and not user.has_usable_password()


@pytest.mark.parametrize("when", ["initial", "locked"])
def test_proof_expiry_is_rechecked_after_waiting_for_stage_a_locks(when, monkeypatch):
    user = account()
    req = proven(user)
    proof = auth.current(req)
    if when == "initial":
        proof.auth_time = timezone.now() - auth.WINDOW - timedelta(seconds=1)
        proof.save(update_fields=["auth_time"])
    else:
        real_current = auth.current

        def age_locked(request, *, lock=False):
            row = real_current(request, lock=lock)
            if lock:
                row.auth_time = timezone.now() - auth.WINDOW - timedelta(seconds=1)
            return row

        monkeypatch.setattr(auth, "current", age_locked)
    with pytest.raises(auth.RecentAuthenticationRequired):
        deletion.request_deletion(req)
    user.refresh_from_db()
    assert user.is_active and user.deletion_requested_at is None


def test_enrollment_email_link_cannot_authorize_deletion(monkeypatch):
    user = account(password=None)
    req = request(user, surface="member")
    send = Mock(return_value=SimpleNamespace(status="sent"))
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", send)
    assert intents.start_email(req) == {"sent": True}
    token = send.call_args.kwargs["text_body"].split("#token=", 1)[1]
    assert intents.confirm_email(req, token) == {"confirmed": True}
    auth.require_enrollment_proof(req)
    with pytest.raises(auth.RecentAuthenticationRequired):
        deletion.request_deletion(req)
    with pytest.raises(AuthenticationFailed):
        intents.confirm_email(req, token)
    assert auth.current(req).auth_time is None


def test_failed_factor_attempt_and_consumed_provider_survive_late_deletion_rollback(monkeypatch):
    user = account()
    SocialIdentity.objects.create(user=user, provider="github", provider_sub="linked")
    req = request(user, surface="member")
    state, parent = intents._new(req, "social_reauth", provider="github", nonce="nonce")
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims", lambda *a, **kw: {"sub": "linked"})
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", lambda **kw: SimpleNamespace(status="sent"))
    result = intents.complete_social(req, state=state, nonce="nonce", code="provider-code")
    row = MFAChallenge.objects.get(token_digest=intents._digest(result["factor_token"]))
    row.context["code_digest"] = "0" * 64
    row.save(update_fields=["context"])
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(req, token=result["factor_token"], code="123456")
    auth.verify(req, password=PASSWORD)
    original = deletion.audit.record

    def fail_commit(actor, action, **kwargs):
        if action == "account.deletion_requested":
            raise RuntimeError("simulate failure before commit")
        return original(actor, action, **kwargs)

    monkeypatch.setattr(deletion.audit, "record", fail_commit)
    with pytest.raises(RuntimeError):
        deletion.request_deletion(req)
    user.refresh_from_db()
    row.refresh_from_db()
    parent.refresh_from_db()
    assert user.is_active and user.deletion_requested_at is None
    assert row.attempts == 1 and row.consumed_at is None and parent.consumed_at
    assert AuditLog.objects.filter(actor=user, action="auth.reauthentication_failed").exists()
    with pytest.raises(AuthenticationFailed):
        intents.complete_social(req, state=state, nonce="nonce")


def configure_sms(monkeypatch):
    monkeypatch.setattr("apps.integrations.sms.sms_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_phone.reserve_platform_otp_sms_quota", lambda: True)
    monkeypatch.setattr("apps.accounts.services_phone.send_sms", lambda **kw: True)
    monkeypatch.setattr("apps.accounts.services_phone._generate_otp", lambda: "654321")


def test_phone_only_proof_commits_attempts_then_allows_deletion(monkeypatch):
    configure_sms(monkeypatch)
    user = account(password=None)
    user.phone_e164, user.phone_verified_at = "+15551234567", timezone.now()
    user.save()
    # Editing a phone clears verification; the OTP seam owns the later stamp.
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    req = request(user, surface="member")
    result = phone.start(req)
    challenge = PhoneVerificationChallenge.objects.get(user=user)
    assert challenge.purpose == "reauth"
    with pytest.raises(AuthenticationFailed):
        phone.confirm(req, token=result["token"], code="000000")
    challenge.refresh_from_db()
    assert challenge.failed_attempts == 1
    assert phone.confirm(req, token=result["token"], code="654321")["verified"]
    with pytest.raises(AuthenticationFailed):
        phone.confirm(req, token=result["token"], code="654321")
    assert deletion.request_deletion(req)["deleted_at"]


def test_attested_device_proof_is_family_bound_and_revoked_on_deletion(settings, monkeypatch):
    user = account(password="strong-device-password")
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])
    verified = client.post("/api/v1/auth/reauth", {"password": "strong-device-password"}, format="json")
    assert verified.status_code == 200
    family = DeviceRefreshFamily.objects.get(user=user)
    second, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert second.status_code == 200
    other = APIClient()
    other.credentials(HTTP_AUTHORIZATION="Bearer " + second.data["access"])
    assert other.post(DELETE, {"confirm": "DELETE"}, format="json").status_code == 403
    rotated = client.post("/api/v1/auth/device/refresh", {"refresh": login.data["refresh"]}, format="json")
    assert rotated.status_code == 200
    client.credentials(HTTP_AUTHORIZATION="Bearer " + rotated.data["access"])
    assert client.post(DELETE, {"confirm": "DELETE"}, format="json").status_code == 202
    family.refresh_from_db()
    assert family.revoked_at
    assert other.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/device/refresh", {"refresh": rotated.data["refresh"]}, format="json").status_code == 401


def test_existing_recent_auth_helper_can_authorize_member_surface_without_staff_membership():
    user = account()
    client = APIClient()
    force_recent_authenticate(client, user, token={"surface": "member"})
    assert client.post(DELETE, {"confirm": "DELETE"}, format="json").status_code == 202
