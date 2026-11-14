"""Decision 508: only explicit re-emission recovers switch-disabled document mail."""
from unittest.mock import patch

import pytest

from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models import MemberNotificationPreference
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot, issue_mail

from tests.billing_docs.email_recovery_helpers import intent_state

pytestmark = pytest.mark.django_db


def set_switch(space, switch, enabled):
    field = "enabled_modules" if switch == "email" else "enabled_features"
    values = set(getattr(space, field))
    if enabled:
        values.add(switch)
    else:
        values.discard(switch)
    setattr(space, field, sorted(values))
    space.save(update_fields=[field])


@pytest.mark.parametrize("switch", ["email", "billing.documents"])
@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_switch_on_alone_never_sends_but_same_intent_reemit_recovers_once(
        document, document_mail, lane, path, switch, django_capture_on_commit_callbacks, mailoutbox):
    original = document_ledger_snapshot(document)
    set_switch(lane.space, switch, False)
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    assert envelope.deliveries.count() == 0
    reason = "Email is disabled for this makerspace." if switch == "email" else "notification_source_disabled"
    assert intent_state(envelope).reason == reason
    history = list(EmailLog.objects.filter(event="document_issued").values())
    assert len(history) == (1 if switch == "email" else 0)
    assert mailoutbox == [] and document_mail.rendered == []
    queued = lane.enqueued.count(envelope.pk)

    with django_capture_on_commit_callbacks(execute=True):
        set_switch(lane.space, switch, True)
    assert lane.enqueued.count(envelope.pk) == queued
    with patch("apps.integrations.notification_tasks.deliver_envelope.delay") as enqueue:
        sweep_notification_outbox()
    assert envelope.pk not in [call.args[0] for call in enqueue.call_args_list]
    # Even a stale worker task and an old skipped log must remain inert.
    deliver_envelope(envelope.pk)
    for log in EmailLog.objects.filter(event="document_issued"):
        _deliver(log)
    assert mailoutbox == [] and document_mail.rendered == []
    assert list(EmailLog.objects.filter(event="document_issued").values()) == history
    assert document_ledger_snapshot(document) == original

    assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf"),
    ]
    sent = assert_mail_owner(document, path, envelope, skipped_direct=len(history))
    assert document_ledger_snapshot(document) == original
    recovered_queue = lane.enqueued.count(envelope.pk)
    assert recovered_queue == queued + (1 if path == "envelope" else 0)
    for _ in range(2):
        assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == recovered_queue
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert assert_mail_owner(document, path, envelope, skipped_direct=len(history)).pk == sent.pk
    assert list(EmailLog.objects.filter(pk__in=[row["id"] for row in history]).values()) == history
    envelope.refresh_from_db()
    assert intent_state(envelope).reason == ""
    # Both owners consume the same persisted generation.
    assert intent_state(envelope).state == "sent"
    assert intent_state(envelope).generation == 1
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_optout_skip_is_permanent_even_after_email_returns_and_consent_changes(
        document, document_mail, lane, path, django_capture_on_commit_callbacks, mailoutbox):
    original = document_ledger_snapshot(document)
    preference = MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
        feature="payments", channel="email", enabled=False)
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    skipped = EmailLog.objects.get(event="document_issued")
    assert (skipped.status, skipped.error) == ("skipped", "email_member_opted_out")
    assert "_disabled_dispatch" not in envelope.routing_snapshot
    history = EmailLog.objects.values().get(pk=skipped.pk)
    set_switch(lane.space, "email", True)
    preference.enabled = True
    preference.save(update_fields=["enabled"])
    for _ in range(2):
        assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
        deliver_envelope(envelope.pk)
        _deliver(skipped)
    assert mailoutbox == [] and document_mail.rendered == []
    assert envelope.deliveries.count() == 0
    assert EmailLog.objects.filter(event="document_issued").count() == 1
    assert EmailLog.objects.values().get(pk=skipped.pk) == history
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("switch", ["email", "billing.documents"])
def test_direct_reserved_mail_disabled_during_delivery_retains_terminal_owner(
        document, document_mail, lane, switch, django_capture_on_commit_callbacks, mailoutbox):
    # Decision 530 makes sent/in-flight reservations terminal for either owner.
    # A positive legacy disabled skip still bootstraps skipped-disabled separately.
    original = document_ledger_snapshot(document)
    with patch("apps.integrations.dispatch._deliver", side_effect=lambda log: log):
        envelope = issue_mail(document, "direct", django_capture_on_commit_callbacks, document_mail)
    pending = EmailLog.objects.get(event="document_issued")
    assert (pending.status, pending.attempts) == ("pending", 0)
    set_switch(lane.space, switch, False)
    _deliver(pending)
    pending.refresh_from_db()
    reason = "Email is disabled for this makerspace." if switch == "email" else "notification_source_disabled"
    assert (pending.status, pending.error, pending.attempts) == ("skipped", reason, 0)
    history = EmailLog.objects.values().get(pk=pending.pk)
    assert mailoutbox == [] and document_mail.rendered == []
    set_switch(lane.space, switch, True)
    _deliver(pending)
    assert mailoutbox == [] and document_mail.rendered == []
    assert issue_mail(document, "direct", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert mailoutbox == [] and document_mail.rendered == []
    assert issue_mail(document, "direct", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert mailoutbox == [] and document_mail.rendered == []
    assert EmailLog.objects.filter(event="document_issued").count() == 1
    assert EmailLog.objects.values().get(pk=pending.pk) == history
    state = intent_state(envelope)
    assert (state.state, state.owner_kind, state.owner_id) == ("sent", "direct", pending.pk)
    assert document_ledger_snapshot(document) == original


def test_two_reemits_before_worker_run_enqueue_recovered_envelope_only_once(
        document, document_mail, lane, django_capture_on_commit_callbacks, mailoutbox):
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "email", True)
    from apps.payments.notifications_p2 import notify_document
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
        notify_document(document)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert mailoutbox == [] and document_mail.rendered == []
    deliver_envelope(envelope.pk)
    deliver_envelope(envelope.pk)
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert_mail_owner(document, "envelope", envelope, skipped_direct=1)


def test_overlapping_direct_dispatch_reservations_reuse_pending_attempt(
        document, document_mail, django_capture_on_commit_callbacks, mailoutbox):
    from apps.integrations.dispatch import dispatch_email
    with patch("apps.integrations.dispatch._deliver", side_effect=lambda log: log) as deliver:
        envelope = issue_mail(document, "direct", django_capture_on_commit_callbacks, document_mail)
        pending = EmailLog.objects.get(event="document_issued")
        # Exercise the dispatch boundary itself: another producer can reach it
        # after checking dedup but before the first reserved attempt finishes.
        duplicate = dispatch_email(makerspace=document.makerspace, to_email=pending.to_email,
            subject="Same document", text_body="Same intent", stream=pending.stream, event=pending.event,
            audience=pending.audience, feature=pending.feature, recipient_id=pending.recipient_id,
            source_kind=pending.source_kind, source_id=pending.source_id,
            source_metadata=pending.source_metadata, sync=True, persist_body=False)
    assert duplicate.pk == pending.pk
    assert deliver.call_count == 1
    assert EmailLog.objects.filter(event="document_issued").count() == 1
    assert (duplicate.status, duplicate.attempts) == ("pending", 0)
    assert mailoutbox == [] and document_mail.rendered == []
    _deliver(pending)
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert assert_mail_owner(document, "direct", envelope).pk == pending.pk


def test_disabled_document_source_does_not_disguise_permanent_optout_on_queued_mail(
        document, document_mail, lane, django_capture_on_commit_callbacks, mailoutbox):
    with patch("apps.integrations.dispatch._deliver", side_effect=lambda log: log):
        envelope = issue_mail(document, "direct", django_capture_on_commit_callbacks, document_mail)
    pending = EmailLog.objects.get(event="document_issued")
    set_switch(lane.space, "billing.documents", False)
    preference = MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
        feature="payments", channel="email", enabled=False)
    _deliver(pending)
    pending.refresh_from_db()
    assert (pending.status, pending.error) == ("skipped", "email_member_opted_out")
    history = EmailLog.objects.values().get(pk=pending.pk)
    set_switch(lane.space, "billing.documents", True)
    preference.enabled = True
    preference.save(update_fields=["enabled"])
    assert issue_mail(document, "direct", django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert mailoutbox == [] and document_mail.rendered == []
    assert EmailLog.objects.filter(event="document_issued").count() == 1
    assert EmailLog.objects.values().get(pk=pending.pk) == history
