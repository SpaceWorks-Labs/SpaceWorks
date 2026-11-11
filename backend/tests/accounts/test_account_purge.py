"""Stage B preserves durable history while scrubbing every mutable identity copy."""

from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.accounts import account_purge as purge
from apps.accounts.models import EmailVerificationChallenge, PasswordResetEnvelope, SocialIdentity
from apps.accounts.models_account_purge import AccountPurgeObject, AccountPurgeProgress, AppleRevocation
from apps.audit.models import AuditLog
from apps.integrations.models import EmailLog
from apps.makerspaces.models import MemberProfile, MemberProject, MembershipRequest
from apps.makerspaces.secrets import encrypt_value
from tests.accounts import deletion_factories as f
from tests.accounts.account_factories import make_membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def archived(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    user = f.identity()
    user.email = "erasure@example.test"
    user.phone = "+15551234567"
    user.first_name = "Private"
    user.display_name = "Private Person"
    user.is_active = False
    user.deletion_requested_at = timezone.now() - timedelta(days=91)
    user.deletion_purge_after = timezone.now() - timedelta(days=1)
    user.deletion_email_ciphertext = encrypt_value(user.email)
    user.save()
    return user


def run(user):
    counts = {"purged": 0, "skipped": 0, "failed": 0}
    purge.purge_account(user.pk, counts)
    user.refresh_from_db()
    return counts


def test_scrubs_copies_keeps_ledger_and_other_peoples_jobs(archived):
    tenant = f.space()
    hardware = f.request(archived, tenant)
    booking = f.booking(archived, tenant, status="completed")
    booking.note, booking.custom_answers = "Personal note", {"secret": "yes"}
    booking.save()
    registration = f.registration(archived, tenant, status="attended", custom_answers={"secret": "yes"})
    legacy = f.service_job(archived, tenant, status="collected", legacy=True)
    legacy.requester_name, legacy.contact_email, legacy.contact_phone = "Private", archived.email, "123"
    legacy.save()
    other = f.identity()
    staff_job = f.service_job(other, tenant, requester=archived, status="collected")
    staff_job.requester_name = "Keep this other member"
    staff_job.save()
    admission = MembershipRequest.objects.create(user=archived, makerspace=tenant, state="canceled",
                                                  invite_email=archived.email, application_answers='{"secret":"yes"}')
    ledger = f.payment(archived, tenant, status="paid_offline")
    original_amount = ledger.amount
    own_email = EmailLog.objects.create(makerspace=tenant, recipient=archived, to_email="old@example.test",
                                        subject="Private", text_body="Private", html_body="Private")
    by_address = EmailLog.objects.create(makerspace=tenant, to_email=archived.email, subject="Private")
    staff_email = EmailLog.objects.create(makerspace=tenant, to_email="staff@example.test", subject="Keep member mention")
    identity = SocialIdentity.objects.create(user=archived, provider="google", provider_sub="subject")
    challenge = EmailVerificationChallenge.objects.create(user=archived, email=archived.email, code_digest="digest",
                                                           expires_at=timezone.now())
    envelope = PasswordResetEnvelope.objects.create(user=archived, email_normalized=archived.email,
                                                     email_fingerprint="fingerprint", digest="digest", requested_at=timezone.now())
    assert run(archived)["purged"] == 1
    for row in (hardware, booking, registration, legacy, staff_job, admission, own_email, by_address, staff_email, ledger):
        row.refresh_from_db()
    assert hardware.requester_username == archived.username
    assert hardware.requester_contact_email == hardware.requester_contact_phone == hardware.requester_name == ""
    assert booking.note == "" and booking.custom_answers is None and booking.phone == "Deleted"
    assert booking.email == f"deleted+{booking.pk}@invalid.invalid"
    assert registration.name == "Deleted member" and registration.phone == "" and registration.custom_answers is None
    assert registration.email == f"deleted+{registration.pk}@invalid.invalid"
    assert legacy.requester_name == legacy.contact_email == legacy.contact_phone == ""
    assert staff_job.requester_name == "Keep this other member"
    assert admission.invite_email == "" and admission.application_answers is None
    assert own_email.to_email == own_email.subject == own_email.text_body == own_email.html_body == ""
    assert by_address.to_email == by_address.subject == ""
    assert staff_email.subject == "Keep member mention"
    assert ledger.amount == original_amount and ledger.member_id == archived.pk
    assert not SocialIdentity.objects.filter(pk=identity.pk).exists()
    assert not EmailVerificationChallenge.objects.filter(pk=challenge.pk).exists()
    assert not PasswordResetEnvelope.objects.filter(pk=envelope.pk).exists()
    assert archived.username.startswith("deleted_") and len(archived.username) == 40
    assert archived.email == archived.phone == archived.first_name == archived.deletion_email_ciphertext == ""
    assert archived.display_name == "Deleted member" and not archived.is_active
    assert archived.account_purged_at
    assert AuditLog.objects.filter(action="account.purged", target_id=str(archived.pk)).count() == 1
    assert run(archived)["purged"] == 0


def test_two_tenant_progress_skips_gate_and_finishes_later(archived, monkeypatch):
    one, two = f.space(), f.space()
    f.request(archived, one)
    f.request(archived, two)
    real_boundary = purge.fanout_tenant_write

    @contextmanager
    def gated(pk, **kwargs):
        if pk == two.pk:
            kwargs["counts"]["skipped"] += 1
            yield False
        else:
            with real_boundary(pk, **kwargs) as allowed:
                yield allowed

    monkeypatch.setattr(purge, "fanout_tenant_write", gated)
    assert run(archived)["skipped"] == 1
    assert AccountPurgeProgress.objects.get(user=archived, makerspace=one).done_at
    assert not archived.account_purged_at and archived.email
    monkeypatch.setattr(purge, "fanout_tenant_write", real_boundary)
    assert run(archived)["purged"] == 1
    assert AccountPurgeProgress.objects.get(user=archived, makerspace=two).done_at


def test_pending_apple_revocation_keeps_global_identity(archived):
    row = AppleRevocation.objects.create(user=archived, client_id="apple-client")
    assert run(archived)["purged"] == 0 and archived.email
    row.done_at = timezone.now()
    row.save()
    assert run(archived)["purged"] == 1


def test_image_failure_retains_journal_then_retries(archived, monkeypatch):
    from apps.accounts import account_purge_objects as objects
    tenant = f.space()
    membership = make_membership(archived, tenant, status="revoked")
    profile = MemberProfile.objects.create(membership=membership, avatar_key="member/avatar.png")
    project = MemberProject.objects.create(profile=profile, title="Project", image_key="member/project.png")
    monkeypatch.setattr("apps.accounts.account_purge_scrub.public_image_storage.object_size", lambda key: 17)
    monkeypatch.setattr(objects, "_client", Mock())
    delete = Mock(side_effect=OSError("storage unavailable"))
    free = Mock()
    monkeypatch.setattr(objects, "delete_all_versions", delete)
    monkeypatch.setattr(objects.limits, "free_storage", free)
    run(archived)
    assert not MemberProfile.objects.filter(pk=profile.pk).exists()
    assert not MemberProject.objects.filter(pk=project.pk).exists()
    assert AccountPurgeObject.objects.filter(user=archived, size_bytes=17, deleted_at__isnull=True, attempts=1).count() == 2
    assert AccountPurgeProgress.objects.get(user=archived, makerspace=tenant).done_at is None
    assert archived.account_purged_at is None
    free.assert_not_called()
    delete.side_effect = None
    run(archived)
    assert archived.account_purged_at and free.call_count == 2
    assert not AccountPurgeObject.objects.filter(user=archived, quota_released_at__isnull=True).exists()


def test_crash_after_byte_delete_resumes_quota_once(archived, monkeypatch):
    from apps.accounts import account_purge_objects as objects
    tenant = f.space()
    row = AccountPurgeObject.objects.create(user=archived, makerspace=tenant, bucket="images", object_key="key", size_bytes=29)
    delete, free = Mock(), Mock()
    monkeypatch.setattr(objects, "_client", Mock())
    monkeypatch.setattr(objects, "delete_all_versions", delete)
    monkeypatch.setattr(objects.limits, "free_storage", free)
    objects.delete_bytes(row.pk)  # First committed step survives a stopped worker.
    row.refresh_from_db()
    assert row.deleted_at and row.quota_released_at is None and row.size_bytes == 29
    objects.drain(archived, tenant.pk)
    objects.drain(archived, tenant.pk)
    delete.assert_called_once()
    free.assert_called_once()


def test_address_snapshot_discovers_unlinked_delivery_tenant(archived):
    tenant = f.space()
    EmailLog.objects.create(makerspace=tenant, to_email=archived.email, subject="Private")
    archived.email = "changed@example.test"
    archived.save(update_fields=["email"])
    assert tenant.pk in purge.alias_tenant_ids(archived)
    assert run(archived)["purged"] == 1


def test_retention_window_is_enforced(archived):
    archived.deletion_purge_after = timezone.now() + timedelta(days=1)
    archived.save()
    assert run(archived)["purged"] == 0


def test_scoped_encryption_rewrites_pii_and_event_blind_indexes(archived):
    from tests.encryption.conftest import enabled_encryption
    from django.db import connection
    with enabled_encryption(dual_read=False):
        tenant = f.space()
        row = f.registration(archived, tenant, status="attended")
        previous_hash = bytes(row.email_exact_hash)
        booking = f.booking(archived, tenant, status="completed")
        booking.note = "private encrypted note"
        booking.save()
        EmailLog.objects.create(makerspace=tenant, to_email=archived.email, subject="Private")
        assert run(archived)["purged"] == 1
        row.refresh_from_db()
        booking.refresh_from_db()
        assert row.email == f"deleted+{row.pk}@invalid.invalid"
        assert bytes(row.email_exact_hash) != previous_hash
        assert booking.note == ""
        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM events_eventregistration WHERE id = %s", [row.pk])
            assert cursor.fetchone()[0] != row.email


def test_image_head_failure_preserves_the_owning_rows_and_keys(archived, monkeypatch):
    tenant = f.space()
    membership = make_membership(archived, tenant, status="revoked")
    profile = MemberProfile.objects.create(membership=membership, avatar_key="member/preserved.png")
    monkeypatch.setattr("apps.accounts.account_purge_scrub.public_image_storage.object_size", Mock(side_effect=OSError("head unavailable")))
    assert run(archived)["failed"] == 1
    profile.refresh_from_db()
    assert profile.avatar_key == "member/preserved.png"
    assert not AccountPurgeObject.objects.filter(user=archived).exists()
    assert not archived.account_purged_at


def test_pending_image_journal_participates_in_tenant_purge_not_migration(archived):
    from apps.makerspaces.storage_key_collectors import collect_public_image_keys
    tenant = f.space()
    AccountPurgeObject.objects.create(user=archived, makerspace=tenant, bucket="public-images",
                                     object_key="member/orphan-retry.png", size_bytes=10)
    assert "member/orphan-retry.png" in collect_public_image_keys(tenant)
    assert "member/orphan-retry.png" not in collect_public_image_keys(tenant, include_coordination=False)
