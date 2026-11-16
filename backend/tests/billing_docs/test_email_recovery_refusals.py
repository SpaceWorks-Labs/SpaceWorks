"""Refused document recovery cannot authorize later channel retries or fallback."""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.integrations.email_preferences import address_hash
from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_history import remove_marker
from tests.billing_docs.test_r2_delivery import provider
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot

from tests.billing_docs.email_recovery_helpers import intent_state

pytestmark = pytest.mark.django_db
DISABLED = "Email is disabled for this makerspace."


def emit_document(document, callbacks):
    document.makerspace.refresh_from_db()
    with callbacks(execute=True):
        notify_document(document)


def mail_history(envelope):
    return list(EmailLog.objects.filter(makerspace_id=envelope.makerspace_id,
        event="document_issued", source_id=envelope.pk).order_by("pk").values())


def assert_direct_skip(row, envelope, error):
    assert (row["status"], row["error"], row["attempts"]) == ("skipped", error, 0)
    assert (row["source_kind"], row["source_id"], row["recipient_id"]) == (
        "notification.direct", envelope.pk, envelope.recipient_id)
    assert row["source_metadata"]["p2_direct"] == envelope.dedup_key


def due_retry(envelope, telegram, attempt, exhausted):
    NotificationDelivery.objects.filter(pk=telegram.pk).update(
        next_attempt_at=timezone.now() - timedelta(seconds=1))
    with patch("apps.integrations.notification_tasks.deliver_envelope.delay") as enqueue:
        sweep_notification_outbox()
    assert [call.args[0] for call in enqueue.call_args_list].count(envelope.pk) == 1
    deliver_envelope(envelope.pk)
    telegram.refresh_from_db()
    state, error, retryable = (("failed", "unavailable", False) if attempt == 4 else
        ("retrying", "unavailable", True) if exhausted else ("accepted", "", False))
    assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
        state, error, attempt, retryable)
    assert (telegram.next_attempt_at is not None) == retryable
    assert telegram.claim_until is None


@pytest.mark.parametrize("pre_marker", [False, True])
@pytest.mark.parametrize("authority", ["inactive", "restricted"])
@pytest.mark.parametrize("exhausted", [False, True])
def test_denied_reemit_cannot_authorize_email_on_other_channel_retry(
        document, document_mail, lane, settings, monkeypatch, pre_marker, authority, exhausted,
        django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    envelope = document_mail.route("envelope")
    owner = document.payment.member
    NotificationPreference.objects.filter(makerspace=lane.space, user=owner, category="payments").update(
        channels=["email", "telegram"], email_fallback=True)
    unavailable = ProviderResult(False, retryable=True, error_code="unavailable")
    fake = provider(monkeypatch, [unavailable] * 4 if exhausted else [
        unavailable, ProviderResult(True, "retry-document-id")])
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    emit_document(document, django_capture_on_commit_callbacks)
    deliver_envelope(envelope.pk)
    telegram = envelope.deliveries.get(channel="telegram")
    assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
        "retrying", "unavailable", 1, True)
    assert telegram.next_attempt_at > timezone.now() and telegram.claim_until is None
    history = mail_history(envelope)
    assert len(history) == 1
    assert_direct_skip(history[0], envelope, DISABLED)
    if pre_marker:
        remove_marker(envelope)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    assert intent_state(envelope).state != "recovery_approved"
    assert document_mail.rendered == [document.pk] and len(fake.documents) == 1
    telegram_history = NotificationDelivery.objects.values().get(pk=telegram.pk)
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "email", True)
    field, denied, restored = (("is_active", False, True) if authority == "inactive" else
                               ("access_status", "restricted", "active"))
    setattr(owner, field, denied)
    owner.save(update_fields=[field])
    assert resolve(envelope) == []
    refused = NotificationEnvelope.objects.values().get(pk=envelope.pk)
    emit_document(document, django_capture_on_commit_callbacks)
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == refused
    assert not refused["routing_snapshot"].get("_disabled_dispatch_reemitted", False)
    assert lane.enqueued.count(envelope.pk) == queued
    assert NotificationDelivery.objects.values().get(pk=telegram.pk) == telegram_history
    assert envelope.deliveries.count() == 1
    assert envelope.deliveries.filter(channel="email").count() == 0
    assert mail_history(envelope) == history
    assert document_ledger_snapshot(document) == original
    smtp.assert_not_called()
    assert mailoutbox == [] and document_mail.rendered == [document.pk]

    setattr(owner, field, restored)
    owner.save(update_fields=[field])
    for attempt in range(2, 5 if exhausted else 3):
        due_retry(envelope, telegram, attempt, exhausted)
        assert len(fake.documents) == attempt and fake.texts == []
        assert document_mail.rendered == [document.pk] * attempt  # Every render belongs to Telegram.
        assert envelope.deliveries.count() == 1
        assert envelope.deliveries.filter(channel="email").count() == 0
        assert mail_history(envelope) == history
        assert EmailLog.objects.filter(event="document_issued").count() == len(history)
        assert document_ledger_snapshot(document) == original
        smtp.assert_not_called()
        assert mailoutbox == []
    assert lane.enqueued.count(envelope.pk) == queued
    telegram_history = NotificationDelivery.objects.values().get(pk=telegram.pk)
    chat_attempts = 4 if exhausted else 2
    for _ in range(2):
        emit_document(document, django_capture_on_commit_callbacks)
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    envelope.refresh_from_db()
    assert intent_state(envelope).state == "sent"
    assert intent_state(envelope).generation == 1
    assert envelope.deliveries.count() == 2
    assert smtp.call_count == 1
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [owner.email]
    assert mailoutbox[0].attachments == [(f"{document.number}.pdf",
        b"%PDF-1.7\nprivate-payer-document-" + str(chat_attempts + 1).encode(), "application/pdf")]
    assert document_mail.rendered == [document.pk] * (chat_attempts + 1)
    assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
    assert len(fake.documents) == chat_attempts and fake.texts == []
    assert NotificationDelivery.objects.values().get(pk=telegram.pk) == telegram_history
    assert list(EmailLog.objects.filter(pk=history[0]["id"]).values()) == history
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("history_kind", [
    "none", "marked", "pre_marker", "authorized_marked", "authorized_pre_marker",
])
@pytest.mark.parametrize("refusal", ["email_member_opted_out", "email_address_suppressed"])
def test_permanent_direct_skip_blocks_other_channel_retries_and_explicit_reemit(
        document, document_mail, lane, settings, monkeypatch, history_kind, refusal,
        django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    envelope = document_mail.route("envelope")
    owner = document.payment.member
    NotificationPreference.objects.filter(makerspace=lane.space, user=owner, category="payments").update(
        channels=["email", "telegram"], email_fallback=True)
    fake = provider(monkeypatch, [ProviderResult(False, retryable=True, error_code="unavailable")] * 4)
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    disabled = history_kind != "none"
    authorized = history_kind.startswith("authorized_")
    if disabled:
        emit_document(document, django_capture_on_commit_callbacks)
        deliver_envelope(envelope.pk)
        first = mail_history(envelope)
        assert len(first) == 1
        assert_direct_skip(first[0], envelope, DISABLED)
        if history_kind.endswith("pre_marker"):
            remove_marker(envelope)
        if authorized:
            # Successful live approval precedes a newly retained permanent refusal.
            # Even this genuine permission cannot override the later refusal.
            set_switch(lane.space, "email", True)
            queued = lane.enqueued.count(envelope.pk)
            emit_document(document, django_capture_on_commit_callbacks)
            envelope.refresh_from_db()
            assert lane.enqueued.count(envelope.pk) == queued + 1
            assert intent_state(envelope).state == "recovery_approved"
            assert intent_state(envelope).generation == 1
            assert envelope.processed_at is None
    if refusal == "email_member_opted_out":
        preference = MemberNotificationPreference.objects.create(makerspace=lane.space, user=owner,
            feature="payments", channel="email", enabled=False)
    else:
        EmailSuppression.objects.create(makerspace=lane.space,
            address_hash=address_hash(lane.space.pk, owner.email), reason="bounce")
    queued = lane.enqueued.count(envelope.pk)
    emit_document(document, django_capture_on_commit_callbacks)
    if not disabled:
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued
    telegram = envelope.deliveries.get(channel="telegram")
    assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
        "retrying", "unavailable", 1, True)
    assert telegram.next_attempt_at > timezone.now() and telegram.claim_until is None
    history = mail_history(envelope)
    assert len(history) == 1 + int(disabled)
    assert_direct_skip(history[-1], envelope, refusal)
    if disabled:
        assert history[0] == first[0]
    envelope.refresh_from_db()
    assert intent_state(envelope).state == "skipped_permanent"
    assert intent_state(envelope).reason == refusal
    assert intent_state(envelope).generation == int(authorized)
    set_switch(lane.space, "email", True)
    if refusal == "email_member_opted_out":
        preference.enabled = True
        preference.save(update_fields=["enabled"])
    else:
        # The original mailbox stays suppressed; current policy allows a new verified one.
        owner.email = "restored-payer@example.test"
        owner.save(update_fields=["email"])
        owner.email_verified_at = timezone.now()
        owner.save(update_fields=["email_verified_at"])
    # Confirm current policy would offer email. Durable intent history must win.
    assert "email" in [target.channel for target in resolve(envelope)]
    for attempt in range(2, 5):
        due_retry(envelope, telegram, attempt, True)
        assert len(fake.documents) == attempt and fake.texts == []
        assert document_mail.rendered == [document.pk] * attempt
        assert envelope.deliveries.count() == 1
        assert envelope.deliveries.filter(channel="email").count() == 0
        assert mail_history(envelope) == history
        assert EmailLog.objects.filter(event="document_issued").count() == len(history)
        assert document_ledger_snapshot(document) == original
        smtp.assert_not_called()
        assert mailoutbox == []
    telegram_history = NotificationDelivery.objects.values().get(pk=telegram.pk)
    assert lane.enqueued.count(envelope.pk) == queued
    envelope.refresh_from_db()
    final_envelope = NotificationEnvelope.objects.values().get(pk=envelope.pk)
    for _ in range(2):
        emit_document(document, django_capture_on_commit_callbacks)
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == final_envelope
    assert envelope.deliveries.count() == 1
    assert envelope.deliveries.filter(channel="email").count() == 0
    assert NotificationDelivery.objects.values().get(pk=telegram.pk) == telegram_history
    assert mail_history(envelope) == history
    assert document_mail.rendered == [document.pk] * 4
    assert len(fake.documents) == 4 and fake.texts == []
    smtp.assert_not_called()
    assert mailoutbox == []
    assert document_ledger_snapshot(document) == original
