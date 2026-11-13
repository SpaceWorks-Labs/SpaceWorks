"""Stage A is atomic, session-bound and repeats discovery under the account lock."""

from datetime import timedelta
import uuid

import pytest
from cryptography.fernet import Fernet
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts import account_deletion as service, reauthentication
from apps.accounts.models import User
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MembershipRequest
from apps.organizations.models import Organization, OrganizationMembership
from apps.tenant_migration.models_source_gate import SourceMigrationGate
from tests.accounts.test_reauthentication import request, PASSWORD, ORIGIN
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
URL = "/api/v1/auth/account/deletion"


@pytest.fixture
def actor(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.ACCOUNT_DELETION_RETENTION_DAYS = 90
    return User.objects.create_user(username="departing", password=PASSWORD, email="departing@example.test")


def proven(actor):
    req = request(actor, surface="member")
    reauthentication.verify(req, password=PASSWORD)
    return req


def membership(user, space):
    return MakerspaceMembership.objects.create(user=user, makerspace=space, role="custom",
        assigned_role=MakerspaceRole.objects.get(makerspace=space, slug="member"))


def test_empty_account_preview_requires_proof_and_never_offers_email(actor):
    result = service.preview(request(actor, surface="member"))
    assert result == {
        "deletable": True, "blockers": [], "reauth": {"required": True, "methods": ["password"]},
        "restorable": True,
        "restore_reason": "Use password recovery or phone sign-in before the purge deadline.",
    }
    actor.set_unusable_password()
    actor.save(update_fields=["password"])
    result = service.preview(request(actor, surface="member"))
    assert result["reauth"]["methods"] == []


def test_email_enrollment_confirmation_is_not_deletion_proof(actor):
    req = request(actor)
    reauthentication.stamp(req, field="enrollment_confirmed_at")
    with pytest.raises(reauthentication.RecentAuthenticationRequired):
        service.request_deletion(req)
    actor.refresh_from_db()
    assert actor.is_active and actor.deletion_requested_at is None


def test_stage_a_revokes_memberships_org_sessions_and_secrets_atomically(actor):
    space = make_space("departures")
    member = membership(actor, space)
    organization = Organization.objects.create(name="Organization", slug="departures")
    org_member = OrganizationMembership.objects.create(organization=organization, user=actor)
    # Disabled pending MFA secrets and recovery material are also removed.
    UserMFA.objects.create(user=actor, secret="encrypted", recovery_digests=["digest"])
    req = proven(actor)
    session = SessionStore()
    session["_auth_user_id"] = str(actor.pk)
    session.save()
    other = SessionStore()
    other["_auth_user_id"] = "999999"
    other.save()
    result = service.request_deletion(req)
    actor.refresh_from_db(); member.refresh_from_db(); org_member.refresh_from_db()
    assert not actor.is_active and not actor.has_usable_password()
    assert actor.deletion_requested_at == result["deleted_at"]
    assert actor.deletion_purge_after - actor.deletion_requested_at == timedelta(days=90)
    assert member.status == "revoked" and member.renewal_cancelled_at
    assert org_member.status == "suspended"
    assert not ReauthenticationSession.objects.filter(user=actor).exists()
    assert not UserMFA.objects.filter(user=actor).exists()
    assert not Session.objects.filter(session_key=session.session_key).exists()
    assert Session.objects.filter(session_key=other.session_key).exists()
    assert OutstandingToken.objects.filter(user=actor, blacklistedtoken__isnull=True).count() == 0
    assert AuditLog.objects.filter(action="account.deletion_requested", actor=actor).count() == 1
    assert AuditLog.objects.filter(action="membership.left", actor=actor).exists()
    assert AuditLog.objects.filter(action="organization.member_departed", actor=actor).exists()
    assert actor.email == "departing@example.test"  # Identity purge belongs to Stage B.


def test_stage_a_cancels_open_applications_as_applicant(actor):
    space = make_space("open-application")
    application = MembershipRequest.objects.create(makerspace=space, user=actor, state="requested")
    service.request_deletion(proven(actor))
    application.refresh_from_db()
    assert application.state == "canceled"


def test_late_failure_rolls_back_every_change(actor, monkeypatch):
    space = make_space("rollback-departure")
    member = membership(actor, space)
    req = proven(actor)
    original = service.audit.record
    def fail_last(actor, action, **kwargs):
        if action == "account.deletion_requested":
            raise RuntimeError("audit unavailable")
        return original(actor, action, **kwargs)
    monkeypatch.setattr(service.audit, "record", fail_last)
    with pytest.raises(RuntimeError):
        service.request_deletion(req)
    actor.refresh_from_db(); member.refresh_from_db()
    assert actor.is_active and actor.has_usable_password() and actor.deletion_requested_at is None
    assert member.status == "active"
    assert ReauthenticationSession.objects.filter(user=actor).exists()
    assert not BlacklistedToken.objects.filter(token__user=actor).exists()
    assert not AuditLog.objects.filter(action="membership.left", actor=actor).exists()


def test_locked_proof_freshness_is_checked_after_initial_check(actor, monkeypatch):
    req = proven(actor)
    original = service.reauthentication.current
    def expired(request, *, lock=False):
        row = original(request, lock=lock)
        if lock:
            row.auth_time = timezone.now() - timedelta(minutes=10, seconds=1)
        return row
    monkeypatch.setattr(service.reauthentication, "current", expired)
    with pytest.raises(reauthentication.RecentAuthenticationRequired):
        service.request_deletion(req)
    actor.refresh_from_db()
    assert actor.is_active


@pytest.mark.parametrize("growing", ["tenant", "organization"])
def test_participation_growth_retries_then_fails_with_typed_503(actor, growing, monkeypatch):
    req = proven(actor)
    name = "tenant_ids" if growing == "tenant" else "organization_ids"
    calls = []
    def changing(user):
        calls.append(user.pk)
        return set() if len(calls) % 2 else {999999}
    monkeypatch.setattr(service, name, changing)
    with pytest.raises(service.DeletionRetry) as exc:
        service.request_deletion(req)
    assert len(calls) == 6 and exc.value.status_code == 503
    assert exc.value.detail["code"] == "deletion_retry"
    actor.refresh_from_db()
    assert actor.is_active


def test_tenant_growth_can_stabilize_on_retry(actor, monkeypatch):
    req = proven(actor)
    space = make_space("new-participation")
    calls = []
    def changing(user):
        calls.append(user.pk)
        return set() if len(calls) == 1 else {space.pk}
    monkeypatch.setattr(service, "tenant_ids", changing)
    assert service.request_deletion(req)["deleted_at"]
    assert len(calls) == 4


def test_gated_historical_membership_refuses_and_audit_survives_rollback(actor):
    space = make_space("gated-departure")
    member = membership(actor, space)
    member.status = "revoked"; member.save(update_fields=["status"])
    now = timezone.now()
    SourceMigrationGate.objects.create(makerspace=space, state="quiesced", owner_id=uuid.uuid4(),
                                       heartbeat_at=now, lease_expires_at=now + timedelta(hours=1))
    req = proven(actor)
    assert service.preview(req)["blockers"][0]["code"] == "makerspace_gated"
    with pytest.raises(service.DeletionBlocked) as exc:
        service.request_deletion(req)
    assert exc.value.status_code == 409
    assert AuditLog.objects.get(action="account.deletion_refused", actor=actor).meta["blocker_codes"] == ["makerspace_gated"]
    actor.refresh_from_db()
    assert actor.is_active and ReauthenticationSession.objects.filter(user=actor).exists()


@pytest.mark.parametrize("kind", ["staff", "platform"])
def test_nonmember_principals_refused_without_member_proof(kind):
    from tests.accounts.account_factories import make_staff
    user = (make_staff(make_space("deletion-staff"), username="deletion-staff") if kind == "staff"
            else User.objects.create_superuser(username="deletion-platform"))
    with pytest.raises(PermissionDenied):
        service.request_deletion(request(user))
    user.refresh_from_db()
    assert user.is_active and user.deletion_requested_at is None


def test_deletion_endpoint_confirmation_openapi_shape_and_cookie_clearing(actor):
    req = proven(actor)
    client = APIClient(); client.force_authenticate(actor, token=req.auth)
    result = client.get(URL)
    assert result.status_code == 200 and result.data["reauth"]["required"] is False
    assert result["Cache-Control"] == "private, no-store"
    assert client.post(URL, {"confirm": "delete"}, format="json").status_code == 400
    result = client.post(URL, {"confirm": "DELETE"}, format="json")
    assert result.status_code == 202 and set(result.data) == {"deleted_at", "purge_after"}
    assert result.cookies["refresh_token"]["max-age"] == 0


def test_locked_blocker_response_preserves_integer_counts(actor, monkeypatch):
    req = proven(actor)
    monkeypatch.setattr(service, "collect", lambda *a, **k: [service.blocker(
        "unpaid_charges", count=2, makerspace_id=123, detail="Settle charges.")])
    client = APIClient(); client.force_authenticate(actor, token=req.auth)
    result = client.post(URL, {"confirm": "DELETE"}, format="json")
    assert result.status_code == 409
    assert result.data["blockers"][0]["count"] == 2
    assert result.data["blockers"][0]["makerspace_id"] == 123


def test_stage_a_revokes_native_families_and_account_only_push_destinations(actor):
    from apps.accounts.models_devices import DeviceGrant, DeviceRefreshToken
    from apps.accounts.services_device_tokens import issue_device_token_pair
    from apps.integrations.models_push import PushDevice
    from tests.accounts.test_reauthentication_deletion import native_request

    req, family = native_request(actor)
    issue_device_token_pair(actor, family.grant, family=family)
    space = make_space("push-only-participation")
    push = PushDevice.objects.create(user=actor, makerspace=space, device_grant=family.grant,
        provider="apns", environment="production", token_ciphertext="encrypted", token_fingerprint="a" * 64)
    reauthentication.verify(req, password=PASSWORD)
    assert service.request_deletion(req)["deleted_at"]
    family.refresh_from_db(); push.refresh_from_db()
    assert family.revoked_at and not push.active and push.invalidated_at
    assert DeviceGrant.objects.get(pk=family.grant_id).status == "revoked"
    assert not DeviceRefreshToken.objects.filter(family=family, blacklisted_at__isnull=True).exists()


def test_locked_restriction_becomes_blocker_with_refusal_audit(actor, monkeypatch):
    from rest_framework.exceptions import AuthenticationFailed
    req = proven(actor)
    current = service.reauthentication.current
    def restrict(request, *, lock=False):
        if lock:
            request.user.access_status = "restricted"
            raise AuthenticationFailed("Account is not available.")
        return current(request, lock=lock)
    monkeypatch.setattr(service.reauthentication, "current", restrict)
    with pytest.raises(service.DeletionBlocked) as exc:
        service.request_deletion(req)
    assert exc.value.blockers[0]["code"] == "access_restricted"
    assert AuditLog.objects.get(action="account.deletion_refused", actor=actor).meta["blocker_codes"] == ["access_restricted"]


def test_failed_factor_attempt_survives_a_later_deletion_refusal(actor, monkeypatch):
    from rest_framework.exceptions import AuthenticationFailed
    from apps.accounts.models_social import SocialIdentity
    from apps.accounts.reauthentication_factors import confirm_factor
    from apps.accounts.reauthentication_intents import _new
    SocialIdentity.objects.create(user=actor, provider="github", provider_sub="linked")
    actor.email_verified_at = timezone.now()
    actor.save(update_fields=["email_verified_at"])
    req = proven(actor)
    token, challenge = _new(req, "social_reauth_factor", provider="github", context={
        "subject": "linked", "method": "email_code", "email": actor.email, "code_digest": "0" * 64,
    })
    with pytest.raises(AuthenticationFailed):
        confirm_factor(req, token=token, code="123456")
    monkeypatch.setattr(service, "collect", lambda *a, **k: [service.blocker(
        "unpaid_charges", detail="Settle charges.")])
    with pytest.raises(service.DeletionBlocked):
        service.request_deletion(req)
    challenge.refresh_from_db()
    assert challenge.attempts == 1 and challenge.consumed_at is None
