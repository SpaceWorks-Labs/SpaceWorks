"""Archive restore fences, authority rechecks, and revoked-authority permanence."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts import account_purge
from apps.accounts.account_restore_email import confirm_email
from apps.accounts.models import User, PasswordResetEnvelope
from apps.accounts.models_account_purge import AccountPurgeObject, AccountPurgeProgress
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts import deletion_factories as f
from tests.accounts.restore_helpers_m1d import PASSWORD, archive, email_proof, email_row, expire, restore_config
from tests.accounts.test_support_m1d import account, m1d_config, purge
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db


def test_restore_requires_new_password_is_single_use_and_audited():
    user = archive()
    old_password = user.password
    token = email_proof(user)
    result = APIClient().post("/api/v1/auth/account/restore/email", {
        "email": user.email, "token": token, "new_password": PASSWORD,
    }, format="json")
    assert result.status_code == 200 and result.data["restored"]
    assert not result.cookies and "access" not in result.data
    user.refresh_from_db()
    assert user.is_active and user.deletion_requested_at is user.deletion_purge_after is None
    assert user.password != old_password and user.check_password(PASSWORD)
    assert AuditLog.objects.filter(action="account.restored", target_id=str(user.pk)).count() == 1
    with pytest.raises(ValidationError):
        confirm_email(user.email, token, PASSWORD)


@pytest.mark.parametrize("password", ["", "123"])
def test_restore_refuses_missing_or_weak_password_without_reactivating(password):
    user = archive()
    with pytest.raises(ValidationError):
        confirm_email(user.email, email_proof(user), password)
    user.refresh_from_db()
    assert not user.is_active and user.deletion_requested_at
    assert email_row(user).attempts == 1


@pytest.mark.parametrize("change", ["generation", "walk_in", "anonymous", "stub", "email", "phone", "restricted"])
def test_rechecks_recovery_eligibility_after_proof_issuance_and_control_promotion(change):
    user = archive()
    email, token = user.email, email_proof(user)
    values = {"generation": {"credential_generation": user.credential_generation + 1},
              "walk_in": {"is_walk_in": True}, "stub": {"is_tenant_dump_stub": True},
              "email": {"email": "changed@example.test"}, "phone": {"phone_e164": "+15551230001"},
              "restricted": {"access_status": "restricted"}}
    if change == "anonymous":
        tenant = f.space()
        tenant.anonymous_requester = user
        tenant.save(update_fields=["anonymous_requester"])
    else:
        # Credential rotation or edits after issuance require a locked recheck. It
        # must read the database, not the original issue-time User instance.
        User.objects.filter(pk=user.pk).update(**values[change])
    with pytest.raises(ValidationError):
        confirm_email(email, token, PASSWORD)
    user.refresh_from_db()
    assert not user.is_active and user.deletion_requested_at
    assert email_row(user).attempts == (0 if change == "email" else 1)


@pytest.mark.parametrize("condition", ["deadline", "past", "fence", "purged"])
def test_restore_refuses_exact_deadline_and_purge_fence(condition, monkeypatch):
    user = archive()
    token = email_proof(user)
    now = timezone.now()
    if condition in {"deadline", "past"}:
        User.objects.filter(pk=user.pk).update(deletion_purge_after=now - timedelta(seconds=condition == "past"))
    else:
        User.objects.filter(pk=user.pk).update(**{ "purge_started_at" if condition == "fence" else "account_purged_at": now})
    monkeypatch.setattr("apps.accounts.account_restore.timezone.now", lambda: now)
    with pytest.raises(ValidationError):
        confirm_email(user.email, token, PASSWORD)


def test_restore_cancels_unrun_purge_work_and_task_skips_restored_user(monkeypatch):
    user, tenant = archive(), f.space()
    AccountPurgeProgress.objects.create(user=user, makerspace=tenant)
    AccountPurgeObject.objects.create(user=user, makerspace=tenant, bucket="public", object_key="not-run", size_bytes=10)
    confirm_email(user.email, email_proof(user), PASSWORD)
    assert not AccountPurgeProgress.objects.filter(user=user).exists()
    assert not AccountPurgeObject.objects.filter(user=user).exists()
    scrub = Mock(side_effect=AssertionError("restored account must never be scrubbed"))
    monkeypatch.setattr(account_purge, "scrub_tenant", scrub)
    assert purge(user)["purged"] == 0
    scrub.assert_not_called()


def test_restoration_keeps_memberships_device_grants_sessions_and_push_revoked():
    from apps.accounts.models import DeviceGrant
    from apps.accounts.models_reauthentication import ReauthenticationSession
    from apps.integrations.models import PushDevice
    from apps.organizations.models import Organization, OrganizationMembership
    from tests.accounts.test_reauthentication_deletion import native_request
    user, tenant = account(), f.space()
    membership = assign_builtin_roles(user, tenant, "member")
    _, family = native_request(user)
    push = PushDevice.objects.create(user=user, makerspace=tenant, device_grant=family.grant,
        token_ciphertext="private", token_fingerprint="a" * 64, provider="apns", environment="production")
    organization = Organization.objects.create(name="Restore organization", slug="restore-organization")
    org_member = OrganizationMembership.objects.create(organization=organization, user=user)
    archive(user)
    confirm_email(user.email, email_proof(user), PASSWORD)
    membership.refresh_from_db()
    org_member.refresh_from_db()
    push.refresh_from_db()
    assert membership.status == "revoked" and org_member.status == "suspended"
    assert not push.active and push.invalidated_at
    assert not DeviceGrant.objects.filter(user=user, revoked_at__isnull=True).exists()
    assert not ReauthenticationSession.objects.filter(user=user).exists()
    assert not MakerspaceMembership.objects.filter(user=user, status="active").exists()


def test_purge_never_starts_before_deadline_and_fence_commits_before_first_scrub(monkeypatch):
    user, tenant = archive(), f.space()
    f.request(user, tenant)
    scrub = Mock()
    monkeypatch.setattr(account_purge, "scrub_tenant", scrub)
    assert purge(user)["purged"] == 0 and user.purge_started_at is None
    scrub.assert_not_called()
    expire(user)
    original = account_purge._scrub
    def check(pk, space):
        assert User.objects.get(pk=pk).purge_started_at is not None
        return original(pk, space)
    monkeypatch.setattr(account_purge, "_scrub", check)
    assert purge(user)["purged"] == 1


def test_after_purge_same_email_creates_new_account_and_old_proof_fails(monkeypatch):
    from apps.accounts.services_registration import register_member
    user = archive()
    address, token = user.email, email_proof(user)
    expire(user)
    assert purge(user)["purged"] == 1 and user.email == ""
    monkeypatch.setattr("apps.accounts.services_registration.issue_challenge", lambda user: None)
    new = register_member(display_name="Returned person", email=address, phone="", password=PASSWORD)
    assert new.pk != user.pk and new.email == address
    with pytest.raises(ValidationError):
        confirm_email(address, token, PASSWORD)


def test_proof_lifetime_and_failed_attempt_cap_commit():
    user = archive()
    token = email_proof(user)
    row = email_row(user)
    assert timedelta(hours=23, minutes=59) < row.expires_at - timezone.now() <= timedelta(hours=24)
    for count in range(1, 6):
        with pytest.raises(ValidationError):
            confirm_email(user.email, "wrong", PASSWORD)
        assert email_row(user).attempts == count
    with pytest.raises(ValidationError):
        confirm_email(user.email, token, PASSWORD)
    PasswordResetEnvelope.objects.filter(pk=row.pk).update(attempts=0, expires_at=timezone.now())
    with pytest.raises(ValidationError):
        confirm_email(user.email, token, PASSWORD)


def test_old_browser_session_and_legacy_access_token_do_not_revive_on_restore():
    from apps.accounts.tokens import SpaceWorksRefreshToken
    from apps.accounts.web_sessions import validate_session
    from rest_framework.exceptions import AuthenticationFailed
    user = account()
    old = SpaceWorksRefreshToken.for_user(user)
    legacy = SpaceWorksRefreshToken.for_user(user, web_session=False)
    archive(user)
    confirm_email(user.email, email_proof(user), PASSWORD)
    user.refresh_from_db()
    assert user.account_restored_at
    for token in (old.access_token, legacy.access_token):
        with pytest.raises(AuthenticationFailed):
            validate_session(user, token)
    fresh = SpaceWorksRefreshToken.for_user(user)
    assert validate_session(user, fresh.access_token)
