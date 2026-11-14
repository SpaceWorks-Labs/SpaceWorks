"""Decision 530: state x event contract, lazy legacy mapping and tenant identity."""
from itertools import product
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.db import IntegrityError, transaction

from apps.integrations.document_email_state import decide, document_identity
from apps.integrations.models import EmailLog
from apps.integrations.models_document_email import DocumentEmailIntent
from tests.billing_docs.test_email_recovery_orderings import DISABLED, business_snapshot

pytestmark = pytest.mark.django_db
STATES = ["initial_pending", "recovery_approved", "skipped_disabled", "skipped_permanent", "sent", "unknown_legacy"]
EVENTS = ["reserve", "disabled", "permanent", "approve", "invalid"]
# Independent specification, not copied from the implementation's transition dict.
EXPECTED = {
    "initial_pending": {"reserve": "sent", "disabled": "skipped_disabled", "permanent": "skipped_permanent"},
    "recovery_approved": {"reserve": "sent", "disabled": "skipped_disabled", "permanent": "skipped_permanent"},
    "skipped_disabled": {"disabled": "skipped_disabled", "permanent": "skipped_permanent", "approve": "recovery_approved"},
    "skipped_permanent": {}, "sent": {}, "unknown_legacy": {},
}


@pytest.mark.parametrize("state,event", list(product(STATES, EVENTS)))
def test_every_changing_transition_and_every_illegal_pair(document, lane, state, event):
    identity = document_identity(document)
    row = DocumentEmailIntent.objects.get(**identity)
    DocumentEmailIntent.objects.filter(pk=row.pk).update(
        state=state, generation=3, reason="", owner_kind="", owner_id=None, email_log=None)
    before = DocumentEmailIntent.objects.values().get(pk=row.pk)
    original = business_snapshot(lane.space)
    log = EmailLog.objects.create(makerspace=lane.space, recipient_id=identity["recipient_id"],
        event="document_issued", source_kind="payments.document", source_id=document.pk)
    callback = Mock(return_value=log)
    reason = DISABLED if event == "disabled" else "email_member_opted_out" if event == "permanent" else ""
    result = decide(**identity, event=event, generation=3, reason=reason, perform=callback, owner_kind="direct")
    target = EXPECTED[state].get(event)
    assert result.allowed is (target is not None)
    row.refresh_from_db()
    assert row.state == (target or state)
    assert row.generation == 3 + int(event == "approve" and target is not None)
    assert callback.call_count == int(target is not None and event in {"reserve", "approve"})
    if target is None:
        assert DocumentEmailIntent.objects.values().get(pk=row.pk) == before
    elif event == "reserve":
        assert (row.owner_kind, row.owner_id, row.email_log_id) == ("direct", log.pk, log.pk)
    elif event in {"disabled", "permanent"}:
        assert row.reason == reason
    assert business_snapshot(lane.space) == original


@pytest.mark.parametrize("state,event", list(product(STATES, ["reserve", "approve", "complete", "skip_log", "attempt"])))
def test_stale_generation_refuses_every_owner_and_completion(document, state, event):
    identity = document_identity(document)
    row = DocumentEmailIntent.objects.get(**identity)
    DocumentEmailIntent.objects.filter(pk=row.pk).update(state=state, generation=2)
    before = DocumentEmailIntent.objects.values().get(pk=row.pk)
    callback = Mock()
    deferred = Mock()
    result = decide(**identity, event=event, generation=1, perform=callback, defer=deferred)
    assert result.allowed is False and result.value is None
    callback.assert_not_called()
    deferred.assert_not_called()
    assert DocumentEmailIntent.objects.values().get(pk=row.pk) == before


@pytest.mark.parametrize("state,event", list(product(STATES, ["inspect", "complete", "attempt", "skip_log"])))
def test_every_unchanging_event_requires_its_exact_state_and_owner(document, lane, state, event):
    identity = document_identity(document)
    row = DocumentEmailIntent.objects.get(**identity)
    DocumentEmailIntent.objects.filter(pk=row.pk).update(state=state, generation=3, email_log=None,
        reason=DISABLED if state == "skipped_disabled" else "email_member_opted_out",
        owner_kind="envelope" if state == "sent" else "", owner_id=101 if state == "sent" else None)
    before = DocumentEmailIntent.objects.values().get(pk=row.pk)
    log = EmailLog.objects.create(makerspace=lane.space, recipient=document.payment.member)
    callback = Mock(return_value=log)
    deferred = Mock(return_value="postponed")
    result = decide(**identity, event=event, generation=3, owner_kind="envelope", owner_id=101,
                    perform=callback, defer=deferred)
    allowed = (event == "complete" and state not in {"initial_pending", "recovery_approved"}
               or event == "attempt" and state == "sent"
               or event == "skip_log" and state in {"skipped_disabled", "skipped_permanent"})
    assert result.allowed is allowed
    assert callback.call_count == int(allowed)
    pending_completion = event == "complete" and state in {"initial_pending", "recovery_approved"}
    assert deferred.call_count == int(pending_completion)
    if pending_completion:
        assert result.value == "postponed"
    after = DocumentEmailIntent.objects.values().get(pk=row.pk)
    assert after == ({**before, "email_log_id": log.pk} if allowed and event == "skip_log" else before)
    if event == "attempt":
        callback.reset_mock()
        assert decide(**identity, event="attempt", owner_kind="direct", owner_id=101, perform=callback).allowed is False
        assert decide(**identity, event="attempt", owner_kind="envelope", owner_id=102, perform=callback).allowed is False
        callback.assert_not_called()


@pytest.mark.parametrize("event", ["approve", "reserve"])
def test_denied_live_admission_consumes_no_permission_and_no_target_reserves_no_owner(document, event):
    identity = document_identity(document)
    row = DocumentEmailIntent.objects.get(**identity)
    DocumentEmailIntent.objects.filter(pk=row.pk).update(state="skipped_disabled" if event == "approve" else "initial_pending")
    before = DocumentEmailIntent.objects.values().get(pk=row.pk)
    callback = Mock()
    refused = decide(**identity, event=event, eligible=False, perform=callback)
    assert refused.allowed is False and refused.value is None
    callback.assert_not_called()
    assert DocumentEmailIntent.objects.values().get(pk=row.pk) == before
    if event == "reserve":
        callback.return_value = None
        empty = decide(**identity, event=event, perform=callback)
        assert empty.allowed is False and empty.value is None
        callback.assert_called_once_with()
        assert DocumentEmailIntent.objects.values().get(pk=row.pk) == before


@pytest.mark.parametrize("facts,expected", [
    ([], "unknown_legacy"), ([("skipped", "")], "unknown_legacy"),
    ([("skipped", DISABLED)], "skipped_disabled"),
    ([("skipped", "notification_source_disabled")], "skipped_disabled"),
    ([("skipped", "email_member_opted_out")], "skipped_permanent"),
    ([("pending", "")], "sent"), ([("sent", "")], "sent"),
    ([("failed", "timeout")], "sent"),
    ([("skipped", DISABLED), ("failed", "timeout")], "sent"),
    ([("skipped", DISABLED), ("pending", "")], "sent"),
    ([("skipped", DISABLED), ("skipped", "email_member_opted_out")], "skipped_permanent"),
])
@pytest.mark.parametrize("retryable", [False, True])
def test_legacy_classification_crosses_direct_representation_once(document, lane, facts, expected, retryable):
    identity = document_identity(document)
    DocumentEmailIntent.objects.filter(**identity).delete()
    for status, error in facts:
        EmailLog.objects.create(makerspace=lane.space, recipient_id=identity["recipient_id"],
            source_kind="payments.document", source_id=document.pk, event="document_issued", status=status,
            error=error, email_retryable=retryable, source_metadata={"p2_direct": identity["intent_key"]})
    history = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    result = decide(**identity, event="inspect")
    assert (result.intent.state, result.intent.generation) == (expected, 0)
    if expected == "sent":
        owner = next(row for row in history if row["status"] in {"pending", "sending", "sent", "failed"})
        assert (result.intent.owner_kind, result.intent.owner_id, result.intent.email_log_id) == (
            "direct", owner["id"], owner["id"])
    # A subsequent 'fresh' assertion cannot reinterpret an already classified legacy intent.
    again = decide(**identity, event="inspect", fresh=True)
    assert (again.intent.pk, again.intent.state) == (result.intent.pk, expected)
    assert list(EmailLog.objects.filter(event="document_issued").order_by("pk").values()) == history


def test_identity_unique_tenant_scoped_and_classified(document, lane):
    from apps.accounts.merge_registry import disposition_for, KEEP_ON_SHELL
    from apps.data_export.classification import OMITTED_MODELS
    from apps.tenant_rls.scope_registry import predicates
    from tests.return_helpers import make_space
    identity = document_identity(document)
    with pytest.raises(IntegrityError), transaction.atomic():
        DocumentEmailIntent.objects.create(**identity)
    callback = Mock()
    with pytest.raises(ValueError, match="Invalid document email owner"):
        decide(**{**identity, "makerspace_id": make_space("document-state-foreign").pk},
               event="reserve", perform=callback)
    with pytest.raises(ValueError, match="Invalid document email owner"):
        decide(**{**identity, "recipient_id": lane.manager.pk}, event="reserve", perform=callback)
    callback.assert_not_called()
    assert disposition_for("integrations.DocumentEmailIntent", "recipient") == KEEP_ON_SHELL
    assert "integrations.DocumentEmailIntent" in OMITTED_MODELS
    assert "integrations.DocumentEmailIntent" in predicates()


# Multi-event R8 specification. A terminal owner's outcome cannot reopen it;
# a no-target pass keeps its usable generation, defers, and refuses completion.
LIFECYCLES = {
    "failed_owner": [("attempt", True, "sent", 0), ("disabled", False, "sent", 0),
        ("approve", False, "sent", 0), ("reserve", False, "sent", 0), ("complete", True, "sent", 0)],
    "queued_owner": [("attempt", True, "sent", 0), ("disabled", False, "sent", 0),
        ("approve", False, "sent", 0), ("reserve", False, "sent", 0), ("complete", True, "sent", 0)],
    "initial_no_target": [("reserve_empty", False, "initial_pending", 0),
        ("complete", False, "initial_pending", 0), ("complete", False, "initial_pending", 0),
        ("approve", False, "initial_pending", 0),
        ("reserve", True, "sent", 0), ("complete", True, "sent", 0)],
    "approved_no_target": [("approve", True, "recovery_approved", 1),
        ("reserve_empty", False, "recovery_approved", 1), ("complete", False, "recovery_approved", 1),
        ("stale_complete", False, "recovery_approved", 1), ("approve", False, "recovery_approved", 1),
        ("reserve", True, "sent", 1), ("complete", True, "sent", 1)],
    "no_target_then_disabled": [("reserve_empty", False, "initial_pending", 0),
        ("complete", False, "initial_pending", 0), ("disabled", True, "skipped_disabled", 0),
        ("complete", True, "skipped_disabled", 0), ("reserve", False, "skipped_disabled", 0),
        ("approve", True, "recovery_approved", 1), ("reserve", True, "sent", 1), ("complete", True, "sent", 1)],
}


@pytest.mark.parametrize("case", LIFECYCLES)
def test_r8_state_event_lifecycles_keep_owner_or_unfinished_permission(document, lane, case):
    identity = document_identity(document)
    owner = EmailLog.objects.create(makerspace=lane.space, recipient_id=identity["recipient_id"],
        source_kind="payments.document", source_id=document.pk, event="document_issued",
        source_metadata={"p2_direct": identity["intent_key"]}, email_retryable=False,
        status="failed" if case == "failed_owner" else "sending" if case == "queued_owner" else "pending")
    if case in {"failed_owner", "queued_owner"}:
        DocumentEmailIntent.objects.filter(**identity).delete()
    else:
        DocumentEmailIntent.objects.filter(**identity).update(generation=0, owner_kind="", owner_id=None,
            email_log=None, reason="", state="skipped_disabled" if case == "approved_no_target" else "initial_pending")
    history = EmailLog.objects.values().get(pk=owner.pk)
    original = business_snapshot(lane.space)
    for event, allowed, state, generation in LIFECYCLES[case]:
        callback = Mock(return_value=None if event == "reserve_empty" else owner)
        deferred = Mock(return_value="postponed")
        result = decide(**identity, event={"reserve_empty": "reserve", "stale_complete": "complete"}.get(event, event),
            reason=DISABLED if event == "disabled" else "", perform=callback, owner_kind="direct", owner_id=owner.pk,
            generation=0 if event == "stale_complete" else None, defer=deferred)
        assert (result.allowed, result.intent.state, result.intent.generation) == (allowed, state, generation)
        assert callback.call_count == int(event == "reserve_empty" or allowed and event in {
            "reserve", "approve", "complete", "attempt"})
        assert deferred.call_count == int(event == "complete" and state in {"initial_pending", "recovery_approved"})
        assert (result.intent.owner_kind, result.intent.owner_id) == (("direct", owner.pk) if state == "sent" else ("", None))
        assert EmailLog.objects.values().get(pk=owner.pk) == history
        assert business_snapshot(lane.space) == original


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("processed", [False, True])
@pytest.mark.parametrize("document_source", [False, True])
def test_held_only_sweep_admission_requires_unfinished_persisted_document_permission(
        document, document_mail, lane, state, processed, document_source):
    from django.utils import timezone
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
    from apps.integrations.notification_tasks import sweep_notification_outbox
    envelope = document_mail.route("envelope")
    retry_at = timezone.now() + timedelta(minutes=5)
    DocumentEmailIntent.objects.filter(**document_identity(document)).update(state=state, generation=4)
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(
        processed_at=timezone.now() if processed else None, available_at=retry_at,
        source_kind="payments.document" if document_source else "payments.ledger",
        event="document_issued" if document_source else "charge_raised")
    sibling = NotificationDelivery.objects.create(makerspace=lane.space, envelope=envelope,
        channel="whatsapp", target_key="held-private-endpoint", provider="twilio", state="held",
        attempt_count=1, ambiguous_count=1, last_error="ambiguous", provider_id="uncertain-acceptance")
    saved = (NotificationEnvelope.objects.values().get(pk=envelope.pk),
        DocumentEmailIntent.objects.values().get(document=document),
        NotificationDelivery.objects.values().get(pk=sibling.pk))
    with patch("apps.integrations.notification_tasks.timezone.now", return_value=retry_at - timedelta(microseconds=1)), patch(
            "apps.integrations.notification_tasks.deliver_envelope.delay") as early:
        sweep_notification_outbox()
    assert [call.args[0] for call in early.call_args_list].count(envelope.pk) == 0
    with patch("apps.integrations.notification_tasks.timezone.now", return_value=retry_at), patch(
            "apps.integrations.notification_tasks.deliver_envelope.delay") as queued:
        sweep_notification_outbox()
    expected = int(document_source and not processed and state in {"initial_pending", "recovery_approved"})
    assert [call.args[0] for call in queued.call_args_list].count(envelope.pk) == expected
    assert (NotificationEnvelope.objects.values().get(pk=envelope.pk),
        DocumentEmailIntent.objects.values().get(document=document),
        NotificationDelivery.objects.values().get(pk=sibling.pk)) == saved
