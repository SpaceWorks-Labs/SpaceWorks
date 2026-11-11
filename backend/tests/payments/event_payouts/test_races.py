"""Real concurrent core commands; adapter emulates G's earlier domain lock port.

Budget release and actual module-purge integration require the sibling R/G suites;
these tests prove the core host/obligation serialization and no Event back-lock.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4
import pytest
from django.db import close_old_connections, connection, transaction
from apps.events.models import Event
from apps.makerspaces.models import Makerspace
from apps.payments.event_payouts import coordination, obligation_workflow, payout_workflow
from apps.payments.event_payouts.decision_workflow import create_locked
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.queries import paid
from apps.payments.event_payouts.transactions import lock_finance_authority
from .conftest import domain_boundary, request_for
from .test_cancel_unpaid import cancel_data
from .test_ledger import ready_payee, record_data

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def attached_prefix(finance_bundle, monkeypatch):
    b = finance_bundle
    class Prefix:
        def lock_before_obligation(self, *, request, seed):
            Event.objects.select_for_update().get(pk=b.event.pk)
            space = Makerspace.objects.select_for_update().get(pk=b.space.pk)
            return space, lock_finance_authority(request.user, space)

        def recheck_locked(self, *, obligation, expected_pool_version):
            assert expected_pool_version == 7

        def close_locked(self, **kwargs):
            assert kwargs["obligation"].state == "cancelled"
    monkeypatch.setattr(coordination, "_provider", SimpleNamespace(resolve=lambda **kwargs: Prefix()))
    return b


def race(left, right):
    barrier = Barrier(2)
    def invoke(fn):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout='8s'")
                cursor.execute("SET statement_timeout='12s'")
            barrier.wait(timeout=8)
            try:
                return ("ok", fn())
            except PayoutError as exc:
                return ("conflict", str(exc.detail["code"]))
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(invoke, fn) for fn in (left, right)]
        return [future.result(timeout=20) for future in futures]


def test_cancel_vs_payout(attached_prefix):
    b = attached_prefix
    payee = ready_payee(b)
    cancellation = {**cancel_data(b.obligation), "expected_pool_version": 7}
    payout = record_data(b.obligation, payee, 10000)
    cancel_request, pay_request = request_for(b.actor, cancellation), request_for(b.actor, payout)
    results = race(lambda: obligation_workflow.cancel_unpaid(request=cancel_request, obligation_id=b.obligation.pk, data=cancellation),
                   lambda: payout_workflow.record(request=pay_request, obligation_id=b.obligation.pk, data=payout))
    assert sorted(result[0] for result in results) == ["conflict", "ok"]
    b.obligation.refresh_from_db()
    assert (b.obligation.state, paid(b.obligation)) in (("cancelled", 0), ("open", 10000))


def test_cancel_vs_decision_correction(attached_prefix):
    b = attached_prefix
    cancellation = {**cancel_data(b.obligation), "expected_pool_version": 7}
    cancel_request = request_for(b.actor, cancellation)
    before = b.obligation.version
    summary = deepcopy(b.snapshot)
    summary["source"].update(decision_uuid=str(uuid4()), decision_sequence=2)
    summary["totals"]["approved_minor"] = summary["lines"][0]["approved_minor"] = 140000
    summary["eligibility"]["core_eligibility_revision"] = b.obligation.eligibility_revision + 1
    def correct():
        with domain_boundary(b):
            return create_locked(makerspace=b.space, event=b.event, owner=b.owner, actor=b.actor,
                operation_id=uuid4(), decision_summary=summary, expected_version=before, expected_revision_sequence=1)
    results = race(lambda: obligation_workflow.cancel_unpaid(request=cancel_request, obligation_id=b.obligation.pk, data=cancellation), correct)
    assert sorted(result[0] for result in results) == ["conflict", "ok"]
    b.obligation.refresh_from_db()
    assert b.obligation.revisions.count() == 2 and b.obligation.approved_minor in (0, 140000)


def test_simultaneous_payouts_cannot_overpay(finance_bundle):
    b = finance_bundle
    payee = ready_payee(b)
    first = record_data(b.obligation, payee, 100000)
    second = {**first, "operation_id": uuid4()}
    requests = [request_for(b.actor, value) for value in (first, second)]
    results = race(*(lambda req=req, data=data: payout_workflow.record(request=req,
        obligation_id=b.obligation.pk, data=data) for req, data in zip(requests, (first, second))))
    assert sorted(result[0] for result in results) == ["conflict", "ok"]
    b.obligation.refresh_from_db()
    assert paid(b.obligation) == 100000 and b.obligation.entries.count() == 1
