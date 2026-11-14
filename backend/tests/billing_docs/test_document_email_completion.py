"""R7: a pass's disabled observation survives a same-generation switch flip."""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.db import connection
from django.utils import timezone

from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_document_email import DocumentEmailIntent
from apps.integrations.notification_outbox import mark_processed
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_history import remove_marker
from tests.billing_docs.test_email_recovery_orderings import DISABLED, business_snapshot

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("switch", ["email", "billing.documents"])
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("restore", ["before_completion", "after_completion"])
def test_same_generation_disabled_pass_releases_unused_approval(
        document, document_mail, lane, settings, monkeypatch, switch, legacy, restore,
        django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    envelope = document_mail.route("envelope")
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
                                          category="payments").update(channels=["email"])
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)

    def emit():
        document.makerspace.refresh_from_db()
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(document)

    reason = DISABLED if switch == "email" else "notification_source_disabled"
    set_switch(lane.space, switch, False)
    emit()
    deliver_envelope(envelope.pk)
    intent = DocumentEmailIntent.objects.get(document=document)
    assert (intent.state, intent.generation, intent.reason) == ("skipped_disabled", 0, reason)
    if legacy:
        if not EmailLog.objects.filter(event="document_issued").exists():
            EmailLog.objects.create(makerspace=lane.space, recipient=document.payment.member,
                source_kind="notification.direct", source_id=envelope.pk, event=envelope.event,
                stream="payments", status="skipped", error=reason,
                source_metadata={"p2_direct": envelope.dedup_key})
        remove_marker(envelope)
    history = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    assert len(history) == int(switch == "email" or legacy)
    assert all((row["status"], row["error"], row["attempts"]) == ("skipped", reason, 0) for row in history)
    original, queued = business_snapshot(lane.space), lane.enqueued.count(envelope.pk)
    set_switch(lane.space, switch, True)
    emit()
    intent = DocumentEmailIntent.objects.get(document=document)
    assert (intent.state, intent.generation) == ("recovery_approved", 1)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    set_switch(lane.space, switch, False)

    def paused_completion(current):
        # Both real reservation loops have finished, but the real completion has not.
        assert current.pk == envelope.pk and current._document_dispatch_epoch == 1
        assert not connection.in_atomic_block  # No lock is held across transport.
        observed = DocumentEmailIntent.objects.get(document=document)
        assert (observed.state, observed.generation, observed.reason) == ("skipped_disabled", 1, reason)
        assert envelope.deliveries.filter(channel="email").count() == 0
        assert EmailLog.objects.filter(event="document_issued").count() == len(history)
        assert smtp.call_count == 0 and document_mail.rendered == [] and mailoutbox == []
        if restore == "before_completion":
            set_switch(lane.space, switch, True)
        mark_processed(current)

    with patch("apps.integrations.notification_outbox.mark_processed", side_effect=paused_completion) as finish:
        deliver_envelope(envelope.pk)
    assert finish.call_count == 1
    intent.refresh_from_db()
    envelope.refresh_from_db()
    assert (intent.state, intent.generation, intent.reason) == ("skipped_disabled", 1, reason)
    assert envelope.processed_at is not None
    if restore == "after_completion":
        set_switch(lane.space, switch, True)
    # Re-enabling alone, stale tasks and sweeps do not use the spent generation.
    with patch("apps.integrations.notification_tasks.deliver_envelope.delay") as sweep:
        sweep_notification_outbox()
    assert envelope.pk not in [call.args[0] for call in sweep.call_args_list]
    deliver_envelope(envelope.pk)
    assert smtp.call_count == 0 and document_mail.rendered == [] and mailoutbox == []
    assert lane.enqueued.count(envelope.pk) == queued + 1
    emit()
    intent.refresh_from_db()
    assert (intent.state, intent.generation) == ("recovery_approved", 2)
    assert lane.enqueued.count(envelope.pk) == queued + 2
    deliver_envelope(envelope.pk)
    leg = envelope.deliveries.get(channel="email")
    log = EmailLog.objects.get(source_kind="notification.envelope", source_id=envelope.pk)
    assert (leg.state, leg.last_error, leg.attempt_count, leg.retryable) == ("sent", "", 1, False)
    assert (log.status, log.error, log.attempts, log.recipient_id) == ("sent", "", 1, document.payment.member_id)
    assert log.source_metadata["delivery_id"] == leg.pk
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [(f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert smtp.call_count == 1 and document_mail.rendered == [document.pk]
    saved = (NotificationEnvelope.objects.values().get(pk=envelope.pk),
             DocumentEmailIntent.objects.values().get(document=document), EmailLog.objects.values().get(pk=log.pk))
    for _ in range(2):
        emit()
        deliver_envelope(envelope.pk)
    assert (NotificationEnvelope.objects.values().get(pk=envelope.pk),
            DocumentEmailIntent.objects.values().get(document=document), EmailLog.objects.values().get(pk=log.pk)) == saved
    assert list(EmailLog.objects.filter(pk__in=[row["id"] for row in history]).order_by("pk").values()) == history
    assert EmailLog.objects.filter(event="document_issued").count() == len(history) + 1
    assert smtp.call_count == 1 and document_mail.rendered == [document.pk] and len(mailoutbox) == 1
    assert lane.enqueued.count(envelope.pk) == queued + 2 and business_snapshot(lane.space) == original


@pytest.mark.parametrize("origin", ["initial", "email:persisted", "email:log", "email:marker",
    "billing.documents:persisted", "billing.documents:log", "billing.documents:marker"])
@pytest.mark.parametrize("refusal", ["standing", "revision"])
@pytest.mark.parametrize("restore", ["before_completion", "after_completion"])
@pytest.mark.parametrize("held_sibling", [False, True])
def test_no_target_completion_preserves_usable_initial_or_approved_work(
        document, document_mail, lane, settings, monkeypatch, origin, refusal, restore, held_sibling,
        django_capture_on_commit_callbacks, mailoutbox):
    from apps.accounts.models import User
    from apps.hardware_requests.models import HardwareRequest
    from apps.integrations.models import DailyEmailCounter
    from apps.payments.document_pdf import render_document_pdf as pdf_render
    from apps.payments.documents import issue_bill
    from apps.payments.models import Payment

    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    envelope = document_mail.route("envelope")
    held = NotificationDelivery.objects.create(makerspace=lane.space, envelope=envelope,
        channel="whatsapp", target_key="held-private-endpoint", provider="twilio", state="held",
        attempt_count=1, ambiguous_count=1, last_error="ambiguous", provider_id="uncertain-acceptance") if held_sibling else None
    held_history = NotificationDelivery.objects.values().get(pk=held.pk) if held else None
    original = business_snapshot(lane.space)
    counters = list(DailyEmailCounter.objects.filter(makerspace=lane.space).values())

    def emit():
        document.makerspace.refresh_from_db()
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(document)

    if origin == "initial":
        loan = HardwareRequest.objects.create(makerspace=lane.space, requester=document.payment.member,
            requester_username=document.payment.member.username, status="accepted")
        debt = Payment.objects.create(makerspace=lane.space, member=document.payment.member,
            subject_type="loan_deposit", subject_id=loan.pk, amount="25.00",
            currency="usd", provider="unclaimed", created_by=lane.manager)
        with django_capture_on_commit_callbacks(execute=True):
            document = issue_bill(debt, actor=lane.manager)
        envelope = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(document.pk))
        if held:
            # The initial branch issues a separate real document intent.
            held.envelope = envelope
            held.save(update_fields=["envelope"])
            held_history = NotificationDelivery.objects.values().get(pk=held.pk)
        original = business_snapshot(lane.space)
        generation, state, recovery_enqueues = 0, "initial_pending", 0
        queued = lane.enqueued.count(envelope.pk)
    else:
        switch, form = origin.split(":")
        reason = DISABLED if switch == "email" else "notification_source_disabled"
        set_switch(lane.space, switch, False)
        emit()
        deliver_envelope(envelope.pk)
        intent = DocumentEmailIntent.objects.get(document=document)
        assert (intent.state, intent.generation, intent.reason) == ("skipped_disabled", 0, reason)
        if held:
            assert NotificationDelivery.objects.values().get(pk=held.pk) == held_history
        if form != "persisted":
            # Both positive legacy forms must work without a state row. Marker
            # form retains no log at all; log form retains no metadata marker.
            if form == "log" and not EmailLog.objects.filter(event="document_issued").exists():
                EmailLog.objects.create(makerspace=lane.space, recipient=document.payment.member,
                    source_kind="notification.direct", source_id=envelope.pk, event=envelope.event,
                    stream="payments", status="skipped", error=reason)
            if form == "marker":
                EmailLog.objects.filter(event="document_issued").delete()
            remove_marker(envelope)
            if form == "marker":
                envelope.routing_snapshot = {**envelope.routing_snapshot, "_disabled_dispatch": reason}
                envelope.save(update_fields=["routing_snapshot"])
        queued = lane.enqueued.count(envelope.pk)
        set_switch(lane.space, switch, True)
        if held:
            # A held sibling must never grant automatic disabled-backlog recovery.
            with patch("apps.integrations.notification_tasks.deliver_envelope.delay") as automatic:
                sweep_notification_outbox()
            assert [call.args[0] for call in automatic.call_args_list].count(envelope.pk) == 0
            deliver_envelope(envelope.pk)
            assert envelope.deliveries.filter(channel="email").count() == 0
            assert lane.enqueued.count(envelope.pk) == queued
        emit()
        generation, state, recovery_enqueues = 1, "recovery_approved", 1
    intent = DocumentEmailIntent.objects.get(document=document)
    assert (intent.state, intent.generation, intent.owner_kind, intent.owner_id) == (state, generation, "", None)
    assert lane.enqueued.count(envelope.pk) == queued + recovery_enqueues
    history = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    assert business_snapshot(lane.space) == original
    assert list(DailyEmailCounter.objects.filter(makerspace=lane.space).values()) == counters
    envelope.refresh_from_db()
    revision = envelope.revision

    def eligibility(enabled):
        if refusal == "standing":
            User.objects.filter(pk=document.payment.member_id).update(is_active=enabled)
        else:
            NotificationEnvelope.objects.filter(pk=envelope.pk).update(revision=revision if enabled else "stale")

    def unlocked_send(*args, **kwargs):
        assert not connection.in_atomic_block
        return smtp_send(*args, **kwargs)

    def unlocked_pdf(row):
        assert not connection.in_atomic_block
        return pdf_render(row)

    smtp = Mock(side_effect=unlocked_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", unlocked_pdf)
    eligibility(False)

    def finish_without_target(current):
        assert current._document_dispatch_epoch == generation
        assert not connection.in_atomic_block
        intent.refresh_from_db()
        assert (intent.state, intent.generation, intent.owner_kind, intent.owner_id) == (state, generation, "", None)
        assert envelope.deliveries.filter(channel="email").count() == 0
        assert list(EmailLog.objects.filter(event="document_issued").order_by("pk").values()) == history
        assert smtp.call_count == 0 and mailoutbox == [] and document_mail.rendered == []
        if restore == "before_completion":
            eligibility(True)
        mark_processed(current)

    completed_at = timezone.now()
    with patch("apps.integrations.notification_outbox.timezone.now", return_value=completed_at), patch(
            "apps.integrations.notification_outbox.mark_processed", side_effect=finish_without_target) as finish:
        deliver_envelope(envelope.pk)
    finish.assert_called_once()
    intent.refresh_from_db()
    envelope.refresh_from_db()
    assert (intent.state, intent.generation, intent.owner_kind, intent.owner_id) == (state, generation, "", None)
    assert envelope.processed_at is None  # No owner means this scheduling pass is unfinished.
    assert envelope.available_at == completed_at + timedelta(minutes=5)
    # Drain broker copies while eligibility is still absent (after_completion)
    # or just restored (before_completion): the retry boundary remains bounded.
    for _ in range(2):
        deliver_envelope(envelope.pk)
    assert smtp.call_count == 0 and document_mail.rendered == [] and mailoutbox == []
    with patch("apps.integrations.notification_tasks.deliver_envelope.delay") as early:
        sweep_notification_outbox()
    assert [call.args[0] for call in early.call_args_list].count(envelope.pk) == 0
    assert list(DailyEmailCounter.objects.filter(makerspace=lane.space).values()) == counters
    assert business_snapshot(lane.space) == original
    if restore == "after_completion":
        eligibility(True)
    emit()
    intent.refresh_from_db()
    assert (intent.state, intent.generation) == (state, generation)
    assert lane.enqueued.count(envelope.pk) == queued + recovery_enqueues
    # Re-emission need not allocate another generation: the approved/initial
    # work is still runnable through the ordinary outbox recovery schedule.
    with patch("apps.integrations.notification_tasks.timezone.now", return_value=envelope.available_at), patch(
            "apps.integrations.notification_tasks.deliver_envelope.delay") as sweep:
        sweep_notification_outbox()
        assert [call.args for call in sweep.call_args_list].count((envelope.pk,)) == 1
        deliver_envelope(envelope.pk)
    leg = envelope.deliveries.get(channel="email")
    log = EmailLog.objects.get(source_kind="notification.envelope", source_id=envelope.pk)
    intent.refresh_from_db()
    envelope.refresh_from_db()
    assert (intent.state, intent.generation, intent.owner_kind, intent.owner_id) == ("sent", generation, "envelope", leg.pk)
    assert envelope.processed_at is not None
    assert (leg.state, leg.last_error, leg.attempt_count, leg.retryable) == ("sent", "", 1, False)
    assert (log.status, log.error, log.attempts, log.recipient_id) == ("sent", "", 1, document.payment.member_id)
    assert log.source_metadata["delivery_id"] == leg.pk
    assert smtp.call_count == 1 and document_mail.rendered == [document.pk]
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [(f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    saved = (NotificationEnvelope.objects.values().get(pk=envelope.pk),
             DocumentEmailIntent.objects.values().get(document=document), EmailLog.objects.values().get(pk=log.pk))
    for _ in range(2):
        emit()
        deliver_envelope(envelope.pk)
    assert (NotificationEnvelope.objects.values().get(pk=envelope.pk),
            DocumentEmailIntent.objects.values().get(document=document), EmailLog.objects.values().get(pk=log.pk)) == saved
    assert list(EmailLog.objects.filter(pk__in=[row["id"] for row in history]).order_by("pk").values()) == history
    assert EmailLog.objects.filter(event="document_issued").count() == len(history) + 1
    assert smtp.call_count == 1 and document_mail.rendered == [document.pk] and len(mailoutbox) == 1
    assert lane.enqueued.count(envelope.pk) == queued + recovery_enqueues
    assert business_snapshot(lane.space) == original
    if held:
        assert NotificationDelivery.objects.values().get(pk=held.pk) == held_history
