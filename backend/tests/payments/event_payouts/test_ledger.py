"""Real DB approval/correction/closure and append/amend/replay acceptance."""
from copy import deepcopy
from datetime import timedelta
import json
from uuid import uuid4
import pytest
from django.db import connection, DatabaseError, transaction
from django.utils import timezone
from apps.payments.event_payouts import eligibility_workflow, payee_workflow, payout_workflow
from apps.payments.event_payouts.decision_workflow import create_locked
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.obligation_models import EventPayoutObligation, EventPayoutObligationRevision
from apps.payments.event_payouts.command_models import EventPayoutCommandReceipt
from apps.payments.event_payouts.payee_models import EventPayeeRevision
from apps.payments.event_payouts.queries import paid
from .conftest import domain_boundary, request_for

pytestmark = pytest.mark.django_db(transaction=True)


def correction(bundle, *, approved, operation_id=None):
    row = EventPayoutObligation.objects.get(pk=bundle.obligation.pk)
    snapshot = deepcopy(bundle.snapshot)
    snapshot["source"].update(decision_uuid=str(uuid4()), decision_sequence=row.source_decision_revision + 1)
    snapshot["totals"]["approved_minor"] = snapshot["lines"][0]["approved_minor"] = approved
    snapshot["eligibility"]["core_eligibility_revision"] = row.eligibility_revision + 1
    snapshot["decision"]["outcome"] = "rejected" if approved == 0 else "partially_approved"
    with domain_boundary(bundle):
        return create_locked(makerspace=bundle.space, event=bundle.event, owner=bundle.owner, actor=bundle.actor,
            decision_summary=snapshot, operation_id=operation_id or uuid4(), expected_version=row.version,
            expected_revision_sequence=row.current_revision.sequence)


def ready_payee(bundle):
    row = EventPayoutObligation.objects.get(pk=bundle.obligation.pk)
    data = {"operation_id": uuid4(), "expected_version": row.version,
            "eligibility_revision": row.eligibility_revision, "reason_code": "verified_attendance"}
    eligibility_workflow.acknowledge(request=request_for(bundle.actor, data), obligation_id=row.pk, data=data)
    payee = EventPayeeRevision.objects.create(obligation=row, owner=bundle.owner, country="IN", template_key="cash",
        template_version=1, method="cash", details=json.dumps({"holder_name": "Private owner"}),
        submitted_at=timezone.now(), disclosure_version=1)
    row.refresh_from_db()
    data = {"operation_id": uuid4(), "expected_version": row.version, "payee_revision_id": payee.pk,
            "expected_payee_version": payee.version, "reason_code": "routing_verified"}
    payee_workflow.review(request=request_for(bundle.actor, data), obligation_id=row.pk, data=data, verified=True)
    payee.refresh_from_db()
    return payee


def record_data(row, payee, amount):
    row.refresh_from_db()
    return {"operation_id": uuid4(), "expected_version": row.version, "amount_minor": amount, "currency": row.currency,
        "method": "cash", "reference": "CASH-RECEIPT-1", "paid_at": timezone.now(), "payee_revision": payee.pk,
        "expected_payee_version": payee.version, "eligibility_revision": row.eligibility_revision}


def test_positive_approval_has_complete_encrypted_core_evidence(finance_bundle):
    b = finance_bundle
    row = EventPayoutObligation.objects.get(pk=b.obligation.pk)
    assert row.current_revision and row.approved_minor == 150000
    assert json.loads(row.current_revision.decision_summary) == b.snapshot
    b.asset.refresh_from_db()
    assert b.asset.obligation_id == row.pk and b.asset.expires_at is None
    with connection.cursor() as cursor:
        cursor.execute("SELECT decision_summary FROM payments_eventpayoutobligationrevision WHERE id=%s", [row.current_revision_id])
        raw = cursor.fetchone()[0]
    assert raw.startswith("pii:gcm:v1:") and "Rail vendor" not in raw


def test_initial_decision_replay_is_durable_and_zero_initial_liability_is_refused(finance_bundle):
    b = finance_bundle
    prior = b.obligation.current_revision
    with domain_boundary(b):
        replay = create_locked(makerspace=b.space, event=b.event, owner=b.owner, actor=b.actor,
            operation_id=prior.operation_id, decision_summary=b.snapshot)
    assert replay.pk == b.obligation.pk and replay.revisions.count() == 1
    snapshot = deepcopy(b.snapshot)
    snapshot["source"].update(claim_uuid=str(uuid4()), decision_uuid=str(uuid4()))
    snapshot["totals"]["approved_minor"] = snapshot["lines"][0]["approved_minor"] = 0
    snapshot["decision"]["outcome"] = "rejected"
    with pytest.raises(PayoutError), domain_boundary(b):
        create_locked(makerspace=b.space, event=b.event, owner=b.owner, actor=b.actor,
            operation_id=uuid4(), decision_summary=snapshot)
    assert EventPayoutObligation.objects.count() == 1


def test_correction_reuses_liability_and_old_evidence_is_immutable(finance_bundle):
    b = finance_bundle
    old_id = b.obligation.current_revision_id
    row = correction(b, approved=140000)
    assert row.pk == b.obligation.pk and row.approved_minor == 140000
    assert row.revisions.count() == 2 and EventPayoutObligation.objects.count() == 1
    assert EventPayoutObligationRevision.objects.get(pk=old_id).approved_minor == 150000
    with pytest.raises(DatabaseError), transaction.atomic():
        EventPayoutObligationRevision.objects.filter(pk=old_id).update(approved_minor=1)
    with pytest.raises(DatabaseError), transaction.atomic():
        EventPayoutObligationRevision.objects.filter(pk=old_id).delete()


def test_missing_evidence_rolls_back_correction_and_closure(finance_bundle):
    b = finance_bundle
    b.snapshot["lines"][0]["receipt"]["generation"] = 999
    before = b.obligation.version
    with pytest.raises(PayoutError):
        correction(b, approved=0)
    b.obligation.refresh_from_db()
    b.asset.refresh_from_db()
    assert b.obligation.version == before and b.obligation.revisions.count() == 1
    assert b.asset.expires_at is None


def test_split_payout_amend_reopens_and_durable_replay_survives_receipt_expiry(finance_bundle):
    b = finance_bundle
    payee = ready_payee(b)
    row = b.obligation
    data = record_data(row, payee, 150000)
    request = request_for(b.actor, data)
    result = payout_workflow.record(request=request, obligation_id=row.pk, data=data)
    row.refresh_from_db(); b.asset.refresh_from_db(); payee.refresh_from_db()
    assert row.state == "settled" and paid(row) == 150000
    assert b.asset.expires_at == row.terminal_financial_at + timedelta(days=2555)
    assert payee.purge_due_at == row.terminal_financial_at + timedelta(days=30)
    from apps.payments.event_payouts.payout_models import EventPayoutEntry
    with pytest.raises(DatabaseError), transaction.atomic():
        EventPayoutEntry.objects.filter(pk=result["entry_id"]).update(amount_minor=1)
    with pytest.raises(DatabaseError), transaction.atomic():
        EventPayoutEntry.objects.filter(pk=result["entry_id"]).delete()
    EventPayoutCommandReceipt.objects.all().delete()
    assert payout_workflow.record(request=request, obligation_id=row.pk, data=data)["entry_id"] == result["entry_id"]
    amendment = {**data, "operation_id": uuid4(), "expected_version": row.version,
                 "amount_minor": 140000, "reason_code": "recording_error", "is_void": False}
    payout_workflow.amend(request=request_for(b.actor, amendment), obligation_id=row.pk, entry_id=result["entry_id"], data=amendment)
    row.refresh_from_db(); b.asset.refresh_from_db()
    assert paid(row) == 140000 and row.state == "open" and b.asset.expires_at is None


def test_fresh_canonical_preflight_refuses_stale_eligible_projection(finance_bundle):
    from dataclasses import replace
    b = finance_bundle
    payee = ready_payee(b)
    b.facts = replace(b.facts, attendance_eligible=False)
    data = record_data(b.obligation, payee, 1)
    with pytest.raises(PayoutError):
        payout_workflow.record(request=request_for(b.actor, data), obligation_id=b.obligation.pk, data=data)
    assert not b.obligation.entries.exists()


def test_zero_correction_closure_failure_rolls_back_summary_and_liability(finance_bundle, monkeypatch):
    b = finance_bundle
    import apps.payments.event_payouts.attachment_workflow as attachments
    close = attachments.close_binding_locked
    def fail(**kwargs):
        close(**kwargs)
        raise RuntimeError("Injected terminal closure failure")
    monkeypatch.setattr(attachments, "close_binding_locked", fail)
    with pytest.raises(RuntimeError):
        correction(b, approved=0)
    b.obligation.refresh_from_db(); b.asset.refresh_from_db()
    assert b.obligation.revisions.count() == 1 and b.obligation.approved_minor == 150000
    assert b.obligation.state == "open" and b.asset.expires_at is None


def test_fresh_evidence_never_silently_clears_a_prior_eligibility_hold(finance_bundle):
    from dataclasses import replace
    from apps.payments.event_payouts.worker_boundary import locked_obligation
    b = finance_bundle
    payee = ready_payee(b)
    b.facts = replace(b.facts, attendance_eligible=False)
    with locked_obligation(b.obligation.pk) as row:
        eligibility_workflow.publish_locked(row, evidence_revision=row.eligibility_revision + 1,
            evidence=b.facts.as_dict(), eligible=False, reason_code="attendance_corrected", actor=b.actor)
    b.facts = replace(b.facts, attendance_eligible=True)
    with locked_obligation(b.obligation.pk) as row:
        eligibility_workflow.publish_locked(row, evidence_revision=row.eligibility_revision + 1,
            evidence=b.facts.as_dict(), eligible=True, reason_code="fresh_venue_scan", actor=b.actor)
    b.obligation.refresh_from_db()
    assert b.obligation.eligibility_status == "needs_acknowledgement"
    data = record_data(b.obligation, payee, 1)
    with pytest.raises(PayoutError):
        payout_workflow.record(request=request_for(b.actor, data), obligation_id=b.obligation.pk, data=data)
