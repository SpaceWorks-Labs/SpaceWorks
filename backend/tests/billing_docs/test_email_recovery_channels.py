"""A completed inbox leg does not own or block a never-reserved document email."""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import EmailLog, NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_history import remove_marker
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot
from tests.billing_docs.test_r2_delivery import provider

from tests.billing_docs.email_recovery_helpers import intent_state

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("pre_marker", [False, True])
def test_successful_inbox_leg_allows_explicit_recovery_of_missing_document_email(
        document, document_mail, lane, pre_marker, django_capture_on_commit_callbacks, mailoutbox):
    envelope = document_mail.route("envelope")
    lane.space.enabled_modules = sorted(set(lane.space.enabled_modules) | {"notifications"})
    lane.space.enabled_features = sorted(set(lane.space.enabled_features) | {"notifications.member_inbox"})
    lane.space.save(update_fields=["enabled_modules", "enabled_features"])
    Matrix.objects.update_or_create(makerspace=lane.space, feature="payments", channel="in_app",
                                    defaults={"enabled": True})
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
        category="payments").update(channels=["email", "in_app"], email_fallback=False)
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    assert envelope.deliveries.count() == 1
    inbox = envelope.deliveries.get(channel="in_app")
    assert (inbox.state, inbox.last_error, inbox.attempt_count) == ("sent", "", 1)
    inbox_history = NotificationDelivery.objects.values().get(pk=inbox.pk)
    history = EmailLog.objects.values().get(event="document_issued")
    assert (history["status"], history["error"]) == ("skipped", "Email is disabled for this makerspace.")
    assert (history["source_kind"], history["source_id"], history["recipient_id"]) == (
        "notification.direct", envelope.pk, document.payment.member_id)
    assert history["source_metadata"]["p2_direct"] == envelope.dedup_key
    if pre_marker:
        remove_marker(envelope)
    else:
        assert intent_state(envelope).reason == "Email is disabled for this makerspace."
    assert mailoutbox == [] and document_mail.rendered == []
    queued = lane.enqueued.count(envelope.pk)

    with django_capture_on_commit_callbacks(execute=True):
        set_switch(lane.space, "email", True)
    deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued
    assert mailoutbox == [] and document_mail.rendered == []
    assert envelope.deliveries.filter(channel="email").count() == 0
    assert NotificationDelivery.objects.values().get(pk=inbox.pk) == inbox_history
    assert EmailLog.objects.values().get(pk=history["id"]) == history

    for _ in range(2):
        document.makerspace.refresh_from_db()
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(document)
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_mail.rendered == [document.pk]
    assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
    assert envelope.deliveries.count() == 2
    assert NotificationDelivery.objects.values().get(pk=inbox.pk) == inbox_history
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("pre_marker", [False, True])
@pytest.mark.parametrize("exhausted", [False, True])
def test_other_channel_retry_cannot_recover_disabled_email_without_explicit_reemit(
        document, document_mail, lane, settings, monkeypatch, pre_marker, exhausted,
        django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    envelope = document_mail.route("envelope")
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
        category="payments").update(channels=["email", "telegram"], email_fallback=True)
    unavailable = ProviderResult(False, retryable=True, error_code="unavailable")
    fake = provider(monkeypatch, [unavailable] * 4 if exhausted else [
        unavailable, ProviderResult(True, "retry-document-id")])
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    assert envelope.deliveries.count() == 1
    telegram = envelope.deliveries.get(channel="telegram")
    assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
        "retrying", "unavailable", 1, True)
    assert telegram.next_attempt_at > timezone.now() and telegram.claim_until is None
    assert len(fake.documents) == 1 and fake.texts == []
    history = EmailLog.objects.values().get(event="document_issued")
    assert (history["status"], history["error"], history["attempts"]) == (
        "skipped", "Email is disabled for this makerspace.", 0)
    assert (history["source_kind"], history["source_id"], history["recipient_id"]) == (
        "notification.direct", envelope.pk, document.payment.member_id)
    assert history["source_metadata"]["p2_direct"] == envelope.dedup_key
    if pre_marker:
        remove_marker(envelope)
    else:
        assert intent_state(envelope).state == "skipped_disabled"
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "email", True)
    for attempt in range(2, 5 if exhausted else 3):
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
        assert len(fake.documents) == attempt and fake.texts == []
        assert envelope.deliveries.filter(channel="email").count() == 0
        assert envelope.deliveries.count() == 1
        assert EmailLog.objects.filter(event="document_issued").count() == 1
        assert EmailLog.objects.values().get(pk=history["id"]) == history
        assert document_ledger_snapshot(document) == original
        smtp.assert_not_called()
        assert mailoutbox == []
    chat_attempts = 4 if exhausted else 2
    assert lane.enqueued.count(envelope.pk) == queued
    assert document_mail.rendered == [document.pk] * chat_attempts
    telegram_history = NotificationDelivery.objects.values().get(pk=telegram.pk)
    for _ in range(2):
        document.makerspace.refresh_from_db()
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(document)
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert smtp.call_count == 1
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [(f"{document.number}.pdf",
        b"%PDF-1.7\nprivate-payer-document-" + str(chat_attempts + 1).encode(), "application/pdf")]
    assert document_mail.rendered == [document.pk] * (chat_attempts + 1)
    assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
    assert envelope.deliveries.count() == 2
    assert len(fake.documents) == chat_attempts and fake.texts == []
    assert NotificationDelivery.objects.values().get(pk=telegram.pk) == telegram_history
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original
