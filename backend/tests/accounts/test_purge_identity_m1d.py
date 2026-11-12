"""All mutable platform and tenant identity copies are erased, idempotently."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.accounts import account_deletion, reauthentication, reauthentication_intents
from apps.accounts.models import EmailVerificationChallenge, PasswordResetEnvelope, SocialIdentity
from apps.accounts.models_account_purge import AppleRefreshCredential, AppleRevocation
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.mfa_crypto import totp
from apps.audit.models import AuditLog
from apps.events.models import EventRegistration
from apps.integrations.models import EmailLog, PushDevice
from apps.makerspaces.models import MembershipRequest
from apps.makerspaces.secrets import encrypt_value
from apps.notifications.models import NotificationInboxRow
from tests.accounts import deletion_factories as f
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_reauthentication import PASSWORD
from tests.accounts.test_reauthentication_deletion import native_request
from tests.accounts.test_support_m1d import account, due, m1d_config, purge
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db


def test_every_platform_identity_field_and_personal_row_is_scrubbed(monkeypatch):
    user, tenant, now = account(), f.space(), timezone.now()
    values = {"first_name": "Private", "last_name": "Person", "display_name": "Private Person",
              "phone": "Private phone", "phone_e164": "+15551234567", "telegram_user_id": "12345",
              "phone_verified_at": now,
              "self_registered_at": now, "last_login": now, "restriction_reason": "Old private reason"}
    for field, value in values.items():
        setattr(user, field, value)
    user.save()
    user.phone_verified_at = now
    user.save(update_fields=["phone_verified_at"])
    identity = SocialIdentity.objects.create(user=user, provider="apple", provider_sub="private-sub")
    AppleRefreshCredential.objects.create(social_identity=identity, client_id="client", token_ciphertext=encrypt_value("secret"))
    credential, secret = enrolled(user, recovery_digests=["private-recovery-digest"])
    req, family = native_request(user)
    push = PushDevice.objects.create(user=user, makerspace=tenant, device_grant=family.grant,
        token_ciphertext="private-token", token_fingerprint="a" * 64, provider="apns", environment="production")
    inbox = NotificationInboxRow.objects.create(user=user, makerspace=tenant, event_key=uuid4(),
        feature="events", event="registered", title="Private")
    rows = [identity, push, inbox,
        EmailVerificationChallenge.objects.create(user=user, email=user.email, code_digest="a" * 64, expires_at=now),
        PhoneVerificationChallenge.objects.create(user=user, phone_e164=user.phone_e164,
            purpose="link", code_digest="b" * 64, expires_at=now),
        PasswordResetEnvelope.objects.create(user=user, email_normalized=user.email, email_fingerprint="c" * 64,
            digest="d" * 64, requested_at=now),
    ]
    _, challenge = reauthentication_intents._new(req, "enrollment_email")
    rows.append(challenge)
    code = totp(secret, int(timezone.now().timestamp() // 30))
    reauthentication.verify(req, password=PASSWORD, code=code)
    monkeypatch.setattr("apps.accounts.apple_revocation._enqueue", lambda user_id: None)
    account_deletion.request_deletion(req)
    assert not UserMFA.objects.filter(pk=credential.pk).exists()
    push.refresh_from_db()
    assert not push.active and push.invalidated_at
    assert AppleRevocation.objects.filter(user=user, done_at__isnull=True).exists()
    # Model a successful revocation before the retention window expires.
    AppleRefreshCredential.objects.filter(social_identity=identity).delete()
    AppleRevocation.objects.filter(user=user).update(done_at=now)
    user.refresh_from_db()
    due(user)
    expected_username = user.deletion_username
    original_request_time = user.deletion_requested_at
    assert purge(user) == {"purged": 1, "failed": 0, "skipped": 0}
    assert user.username == expected_username and user.username.startswith("deleted_")
    assert len(user.username) == 40 and user.display_name == "Deleted member"
    for field in ("email", "phone", "phone_e164", "first_name", "last_name", "telegram_user_id",
                  "deletion_email_ciphertext", "deletion_username", "restriction_reason"):
        assert getattr(user, field) == "", field
    for field in ("email_verified_at", "phone_verified_at", "self_registered_at", "last_login"):
        assert getattr(user, field) is None, field
    assert not user.is_active and not user.has_usable_password()
    assert user.deletion_requested_at == original_request_time and user.account_purged_at
    for row in rows:
        assert not type(row).objects.filter(pk=row.pk).exists(), type(row).__name__
    snapshot = type(user).objects.filter(pk=user.pk).values().get()
    assert purge(user)["purged"] == 0
    assert type(user).objects.filter(pk=user.pk).values().get() == snapshot
    assert AuditLog.objects.filter(action="account.purged", target_id=str(user.pk)).count() == 1


@pytest.mark.parametrize("encrypted", [False, True], ids=["plaintext", "scoped-pii"])
def test_every_mutable_tenant_copy_is_scrubbed_without_touching_other_members(encrypted):
    from contextlib import nullcontext
    with enabled_encryption(dual_read=False) if encrypted else nullcontext():
        user, other, tenant = due(account()), account(), f.space()
        hardware = f.request(user, tenant)
        hardware.requester_name, hardware.requester_contact_email, hardware.requester_contact_phone = "Private", user.email, "123"
        hardware.save()
        booking = f.booking(user, tenant, status="completed")
        booking.note, booking.custom_answers = "Private note", {"secret": "Private"}
        booking.save()
        registration = f.registration(user, tenant, status="attended", custom_answers={"secret": "Private"})
        second_registration = EventRegistration.objects.create(event=registration.event, member=user,
            name="Private", email="alternate@example.test", phone="123", status="cancelled")  # one ACTIVE registration per member and event
        jobs = [f.service_job(user, tenant, status="collected", legacy=legacy) for legacy in (False, True)]
        for job in jobs:
            job.requester_name, job.contact_email, job.contact_phone = "Private", user.email, "123"
            job.save()
        other_job = f.service_job(other, tenant, requester=user, status="collected")
        admission = MembershipRequest.objects.create(user=user, makerspace=tenant, state="canceled",
            invite_email=user.email, application_answers='{"secret":"Private"}')
        own = EmailLog.objects.create(makerspace=tenant, recipient=user, to_email="old@example.test",
            subject="Private", text_body="Private", html_body="Private")
        address_only = EmailLog.objects.create(makerspace=tenant, to_email=user.email.upper(),
            subject="Private", text_body="Private", html_body="Private")
        platform = EmailLog.objects.create(recipient=user, to_email=user.email,
            subject="Private", text_body="Private", html_body="Private")
        staff = EmailLog.objects.create(makerspace=tenant, to_email=other.email, subject="Mention of Private",
            text_body="Member's retained operational history", html_body="Retained")
        other_snapshot = type(other_job).objects.filter(pk=other_job.pk).values().get()
        staff_snapshot = EmailLog.objects.filter(pk=staff.pk).values().get()
        assert purge(user)["purged"] == 1
        hardware.refresh_from_db()
        assert hardware.requester_username == user.username
        assert hardware.requester_name == hardware.requester_contact_email == hardware.requester_contact_phone == ""
        booking.refresh_from_db()
        assert booking.name == "Deleted member" and booking.phone == "Deleted"
        assert booking.email == f"deleted+{booking.pk}@invalid.invalid"
        assert booking.note == "" and booking.custom_answers is None
        for row in (registration, second_registration):
            row.refresh_from_db()
            assert row.name == "Deleted member" and row.phone == "" and row.custom_answers is None
            assert row.email == f"deleted+{row.pk}@invalid.invalid"
        assert registration.email != second_registration.email
        for row in jobs:
            row.refresh_from_db()
            assert row.requester_name == row.contact_email == row.contact_phone == ""
        admission.refresh_from_db()
        assert admission.invite_email == "" and admission.application_answers is None
        for row in (own, address_only, platform):
            row.refresh_from_db()
            assert row.to_email == row.subject == row.text_body == row.html_body == ""
        assert type(other_job).objects.filter(pk=other_job.pk).values().get() == other_snapshot
        assert EmailLog.objects.filter(pk=staff.pk).values().get() == staff_snapshot
        assert purge(user)["purged"] == 0


def test_future_retention_deadline_preserves_identity():
    user = due(account())
    user.deletion_purge_after = timezone.now() + timedelta(days=1)
    user.save()
    assert purge(user)["purged"] == 0
    assert user.email and not user.account_purged_at


def test_stage_a_address_snapshot_finds_and_scrubs_old_address_only_logs():
    user, tenant = due(account()), f.space()
    old_email = user.email
    row = EmailLog.objects.create(makerspace=tenant, to_email=old_email,
        subject="Private", text_body="Private", html_body="Private")
    user.email = "replacement@example.test"
    user.save(update_fields=["email"])
    assert purge(user)["purged"] == 1
    row.refresh_from_db()
    assert row.to_email == row.subject == row.text_body == row.html_body == ""
