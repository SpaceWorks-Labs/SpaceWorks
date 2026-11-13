"""Durable cancellation, closure rollback, and current live/session authority."""
from copy import deepcopy
from datetime import timedelta
import json
from uuid import uuid4
import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied
from apps.accounts.models import User
from apps.payments.event_payouts import obligation_workflow, coordination
from apps.payments.event_payouts.command_models import EventPayoutCommandReceipt
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.purge import detach_locked
from .conftest import domain_boundary, request_for
from .test_ledger import ready_payee, record_data

pytestmark = pytest.mark.django_db(transaction=True)


def detach(bundle):
    with domain_boundary(bundle):
        row = EventPayoutObligation.objects.select_for_update().get(pk=bundle.obligation.pk)
        detach_locked([row], actor=bundle.actor, operation_id=uuid4(), facts_by_obligation={row.pk: bundle.facts})
    bundle.obligation.refresh_from_db()


def cancel_data(row):
    row.refresh_from_db()
    return {"operation_id": uuid4(), "expected_version": row.version,
        "expected_revision_sequence": row.current_revision.sequence, "expected_pool_version": None,
        "reason_code": "no_liability", "note": "Finance cancelled the unpaid obligation."}


def test_cancel_unpaid_durable_replay(finance_bundle, monkeypatch):
    b = finance_bundle
    detach(b)
    def forbidden(*args, **kwargs):
        raise AssertionError("Detached cancellation cannot call a domain provider.")
    monkeypatch.setattr(coordination, "_provider", type("Forbidden", (), {"resolve": forbidden})())
    original = b.obligation.current_revision.decision_summary
    data = cancel_data(b.obligation)
    request = request_for(b.actor, data)
    first = obligation_workflow.cancel_unpaid(request=request, obligation_id=b.obligation.pk, data=data)
    EventPayoutCommandReceipt.objects.all().delete()
    again = obligation_workflow.cancel_unpaid(request=request, obligation_id=b.obligation.pk, data=data)
    assert first["cancellation_revision_id"] == again["cancellation_revision_id"]
    b.obligation.refresh_from_db()
    assert b.obligation.revisions.count() == 2 and b.obligation.state == "cancelled"
    assert b.obligation.current_revision.decision_summary == original
    with pytest.raises(PayoutError):
        obligation_workflow.cancel_unpaid(request=request, obligation_id=b.obligation.pk, data={**data, "note": "Different"})


def test_cancel_unpaid_atomic_retention_closure(finance_bundle, monkeypatch):
    b = finance_bundle
    payee = ready_payee(b)
    detach(b)
    data = cancel_data(b.obligation)
    original = __import__("apps.payments.event_payouts.attachment_workflow", fromlist=["close_binding_locked"]).close_binding_locked
    def fail(**kwargs):
        original(**kwargs)
        raise RuntimeError("Injected late closure failure")
    monkeypatch.setattr("apps.payments.event_payouts.attachment_workflow.close_binding_locked", fail)
    with pytest.raises(RuntimeError):
        obligation_workflow.cancel_unpaid(request=request_for(b.actor, data), obligation_id=b.obligation.pk, data=data)
    b.obligation.refresh_from_db(); b.asset.refresh_from_db(); payee.refresh_from_db()
    assert b.obligation.state == "open" and b.asset.expires_at is None and payee.purge_due_at is None
    assert b.obligation.revisions.count() == 1
    monkeypatch.setattr("apps.payments.event_payouts.attachment_workflow.close_binding_locked", original)
    obligation_workflow.cancel_unpaid(request=request_for(b.actor, data), obligation_id=b.obligation.pk, data=data)
    b.obligation.refresh_from_db(); b.asset.refresh_from_db(); payee.refresh_from_db()
    assert b.asset.expires_at == b.obligation.terminal_financial_at + timedelta(days=2555)
    assert payee.purge_due_at == b.obligation.terminal_financial_at + timedelta(days=30)


def test_cancel_unpaid_authority_reauth_versions(finance_bundle):
    b = finance_bundle
    detach(b)
    data = cancel_data(b.obligation)
    with pytest.raises(PermissionDenied):
        obligation_workflow.cancel_unpaid(request=request_for(b.actor, data, reauth=False), obligation_id=b.obligation.pk, data=data)
    with pytest.raises(PayoutError):
        obligation_workflow.cancel_unpaid(request=request_for(b.actor, data), obligation_id=b.obligation.pk,
            data={**data, "expected_revision_sequence": 999})
    with pytest.raises(PayoutError):
        obligation_workflow.cancel_unpaid(request=request_for(b.owner, data), obligation_id=b.obligation.pk, data=data)
    b.space.archived_at = timezone.now()
    b.space.save(update_fields=["archived_at"])
    with pytest.raises(APIException) as refusal:
        obligation_workflow.cancel_unpaid(request=request_for(b.actor, data), obligation_id=b.obligation.pk, data=data)
    assert refusal.value.status_code in (401, 403, 404)
    b.obligation.refresh_from_db()
    assert b.obligation.state == "open" and b.obligation.revisions.count() == 1


def test_detached_settlement_requires_explicit_retained_evidence_acknowledgement(finance_bundle, monkeypatch):
    from apps.payments.event_payouts import eligibility_workflow, payout_workflow, preflight
    b = finance_bundle
    payee = ready_payee(b)
    detach(b)
    def forbidden(**kwargs):
        raise AssertionError("Detached finance must never consult domain runtime.")
    monkeypatch.setattr(preflight, "_provider", type("Reader", (), {"read": staticmethod(forbidden)})())
    payout = record_data(b.obligation, payee, 1)
    with pytest.raises(PayoutError):
        payout_workflow.record(request=request_for(b.actor, payout), obligation_id=b.obligation.pk, data=payout)
    b.obligation.refresh_from_db()
    ack = {"operation_id": uuid4(), "expected_version": b.obligation.version,
        "eligibility_revision": b.obligation.eligibility_revision, "reason_code": "retained_evidence_verified"}
    eligibility_workflow.acknowledge(request=request_for(b.actor, ack), obligation_id=b.obligation.pk, data=ack)
    payout = record_data(b.obligation, payee, 1)
    assert payout_workflow.record(request=request_for(b.actor, payout), obligation_id=b.obligation.pk, data=payout)["entry_id"]
