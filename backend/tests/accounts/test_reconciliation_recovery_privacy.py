"""Recovery and erasure own an account ID, never another kind's shared contact."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.account_purge import _global_rows
from apps.accounts.account_purge_scrub import scrub_email_logs
from apps.accounts.account_restore import identifier_fingerprint
from apps.accounts.account_restore_email import confirm_email
from apps.accounts.models import PasswordResetEnvelope, User
from apps.accounts.password_reset_crypto import credential_fingerprint, otp_digest
from apps.accounts.services_password_reset import confirm_password_reset, request_password_reset
from apps.accounts.services_password_reset_drain import claim_pending_envelopes, prepare_delivery
from apps.integrations.models import EmailLog
from tests.accounts.account_factories import make_staff
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
PASSWORD = "Recovered-private-account-749!"


def accounts():
    space = make_space("recovery-isolation")
    member = User.objects.create_user(username="recover-member", email="shared-recovery@example.test",
                                      password=PASSWORD)
    staff = make_staff(space, username="recover-staff", email="recover-staff@example.test", password=PASSWORD)
    return member, staff


def envelope(user, *, purpose="reset", code="123456"):
    now = timezone.now()
    return PasswordResetEnvelope.objects.create(user=user, context=user.account_kind,
        makerspace_id=user.staff_makerspace_id, purpose=purpose, email_normalized=user.email,
        email_fingerprint="a" * 64, digest=otp_digest(code, user.email), digest_is_live=True,
        credential_generation=user.credential_generation, status="issued", generation=1,
        requested_at=now, expires_at=now + timedelta(hours=24),
        credential_fingerprint=identifier_fingerprint(user) if purpose == "restore"
        else credential_fingerprint(user, user.email))


def archive(user):
    user.is_active = False
    user.set_unusable_password()
    user.deletion_requested_at = timezone.now()
    user.deletion_purge_after = timezone.now() + timedelta(days=90)
    user.save(update_fields=["is_active", "password", "deletion_requested_at", "deletion_purge_after"])


def test_restore_never_consumes_staff_otp_sharing_member_email():
    member, staff = accounts()
    staff_row = envelope(staff)  # Lower PK deliberately defeats an email-only .first().
    archive(member)
    member_row = envelope(member, purpose="restore", code="restore-secret")
    with pytest.raises(ValidationError):
        confirm_email(member.email, "123456", PASSWORD)
    staff_row.refresh_from_db()
    assert staff_row.attempts == 0 and staff_row.consumed_at is None and staff_row.digest_is_live
    assert confirm_email(member.email, "restore-secret", PASSWORD).pk == member.pk
    member_row.refresh_from_db()
    assert member_row.status == "consumed" and member_row.attempts == 2
    staff.refresh_from_db()
    assert staff.is_active and staff.credential_generation == 0


def test_restore_proof_is_refused_by_reset_service_and_attempt_is_durable():
    member, _ = accounts()
    archive(member)
    row = envelope(member, purpose="restore", code="123456")
    with pytest.raises(ValidationError):
        confirm_password_reset(member.email, "123456", PASSWORD)
    row.refresh_from_db()
    assert row.attempts == 1 and row.status == "discarded" and not row.digest_is_live
    member.refresh_from_db()
    assert not member.is_active


def test_member_global_purge_does_not_delete_staff_reset_envelope(monkeypatch):
    member, staff = accounts()
    envelope(member)
    staff_row = envelope(staff)
    # Other domains are checked through their owner APIs in cross-lane tests.
    monkeypatch.setattr("apps.accounts.account_purge.scrub_email_logs", lambda *args: None)
    _global_rows(member)
    assert not PasswordResetEnvelope.objects.filter(user=member).exists()
    assert PasswordResetEnvelope.objects.filter(pk=staff_row.pk, user=staff).exists()


def test_email_scrub_preserves_staff_and_ambiguous_address_only_history():
    member, staff = accounts()
    logs = [EmailLog.objects.create(recipient=recipient, to_email=member.email,
                subject="Private subject", text_body="Private body", status="sent")
            for recipient in (member, staff, None)]
    scrub_email_logs(member, None, member.email)
    for row in logs:
        row.refresh_from_db()
    assert logs[0].subject == logs[0].to_email == ""
    # U-A1: an address belongs to exactly one person, so an address-only row for it is not ambiguous any more
    # and is scrubbed too; another account's own history stays.
    assert logs[2].subject == logs[2].to_email == ""
    assert logs[1].subject == "Private subject"


@pytest.mark.parametrize("kind", ["platform"])  # a staff-track holder is a person (U-A1)
def test_database_refuses_nonmember_deletion_state(kind):
    member, staff = accounts()
    user = staff if kind == "staff" else User.objects.create_superuser(
        username="recovery-platform", email="recovery-platform@example.test", password=PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(deletion_requested_at=timezone.now())


def test_drain_fences_a_request_from_before_restoration(monkeypatch):
    member, _ = accounts()
    request_password_reset(member.email)
    User.objects.filter(pk=member.pk).update(account_restored_at=timezone.now())
    claim = claim_pending_envelopes()[0]
    assert prepare_delivery(claim) == "discarded"
    assert not PasswordResetEnvelope.objects.get(user=member).digest_is_live


def test_apple_revocation_and_stored_refresh_credentials_are_member_only():
    from apps.accounts.apple_revocation import schedule_revocations
    from apps.accounts.models import SocialIdentity
    from apps.accounts.models_account_purge import AppleRefreshCredential, AppleRevocation
    from rest_framework.exceptions import PermissionDenied

    root = User.objects.create_superuser(username="apple-platform", password=PASSWORD)
    # Historical provider links confer no member login or lifecycle authority.
    identity = SocialIdentity.objects.create(user=root, provider="apple", provider_sub="old-platform-link")
    with pytest.raises(PermissionDenied):
        schedule_revocations(root)
    with pytest.raises(IntegrityError), transaction.atomic():
        AppleRefreshCredential.objects.create(social_identity=identity, client_id="app", token_ciphertext="opaque")
    with pytest.raises(IntegrityError), transaction.atomic():
        AppleRevocation.objects.create(user=root, client_id="app")
