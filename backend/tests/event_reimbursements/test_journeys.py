"""AO19 service journeys on PostgreSQL with real core writers and admission ports."""
import json
from uuid import UUID
import pytest
from django.db import connection
from django.utils import timezone
from apps.event_reimbursements import claim_workflow
from apps.event_reimbursements.budget_models import BudgetReservation
from apps.event_reimbursements.projections import claim_detail
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts import payee_workflow, payout_workflow
from apps.payments.event_payouts.payout_models import EventPayoutEntry
from apps.payments.event_payouts.queries import paid
from .conftest import cmd, keyed
from .helpers import submitted, decision_data

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("hackathon", [False, True], ids=["ordinary-inline-request", "hackathon-admission-rsvp"])
def test_ordinary_and_hackathon_full_reimbursement_journey(make_world, monkeypatch, hackathon):
    world = make_world(hackathon=hackathon)
    claim, asset, line_id = submitted(world, monkeypatch, inline=not hackathon)
    data = decision_data(world, claim, line_id, 7000, outcome="partially_approved")
    result = claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=data)
    assert claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=data) == result
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    assert obligation.approved_minor == 7000
    asset.refresh_from_db()
    assert asset.obligation_id == obligation.pk
    data = cmd(obligation.version, expected_payee_version=None, country="IN", method="cash", template_key="cash",
        template_version=1, details={"holder_name": "Private payee"}, disclosure_version=1)
    payee_result = payee_workflow.put(request=keyed(world.member_session, data), obligation_id=obligation.pk, data=data)
    obligation.refresh_from_db()
    payee_id = UUID(payee_result["payee_revision_id"])
    data = cmd(obligation.version, payee_revision_id=payee_id, expected_payee_version=payee_result["payee_version"])
    payee_workflow.review(request=keyed(world.finance, data), obligation_id=obligation.pk, verified=True, data=data)
    from apps.payments.event_payouts import eligibility_workflow
    obligation.refresh_from_db()
    data = cmd(obligation.version, eligibility_revision=obligation.eligibility_revision, reason_code="verified_attendance")
    eligibility_workflow.acknowledge(request=keyed(world.finance, data), obligation_id=obligation.pk, data=data)
    original = None
    for amount in (3000, 4000):
        obligation.refresh_from_db()
        payee = obligation.payee_revisions.get(pk=payee_id)
        value = cmd(obligation.version, amount_minor=amount, currency="INR", method="cash", reference="CASH-TEST",
            paid_at=timezone.now(), payee_revision=payee_id, expected_payee_version=payee.version,
            eligibility_revision=obligation.eligibility_revision)
        response = payout_workflow.record(request=keyed(world.finance, value), obligation_id=obligation.pk, data=value)
        assert payout_workflow.record(request=keyed(world.finance, value), obligation_id=obligation.pk, data=value)["entry_id"] == response["entry_id"]
        original = EventPayoutEntry.objects.get(pk=response["entry_id"])
    obligation.refresh_from_db(); world.pool.refresh_from_db(); claim.refresh_from_db()
    assert paid(obligation) == 7000
    assert claim.state == "partially_approved"
    assert claim_detail(claim, owner=True)["display_state"] == "paid"
    assert (world.pool.reserved_minor, world.pool.committed_minor) == (0, 7000)
    assert BudgetReservation.objects.get(award=claim.award).committed_minor == 7000
    assert EventPayoutEntry.objects.filter(obligation=obligation).count() == 2
    data = cmd(obligation.version, expected_tip_id=original.pk, historical_correction=True,
            amount_minor=original.amount_minor, currency="INR", method="cash", reference="CASH-CORRECTED",
            paid_at=original.paid_at, payee_revision=payee_id,
            expected_payee_version=obligation.payee_revisions.get(pk=payee_id).version,
            eligibility_revision=obligation.eligibility_revision, reason_code="other", is_void=False)
    correction = payout_workflow.amend(request=keyed(world.finance, data), obligation_id=obligation.pk,
        entry_id=original.pk, data=data)
    amended = EventPayoutEntry.objects.get(pk=correction["entry_id"])
    original.refresh_from_db(); obligation.refresh_from_db()
    assert original.reference == "CASH-TEST" and amended.reference == "CASH-CORRECTED"
    assert amended.amends_id == original.pk and amended.chain_uuid == original.chain_uuid
    assert paid(obligation) == 7000 and EventPayoutEntry.objects.filter(obligation=obligation).count() == 3
    # The mandatory core evidence is encrypted even with optional PII off.
    with connection.cursor() as cursor:
        cursor.execute("SELECT decision_summary FROM payments_eventpayoutobligationrevision WHERE id=%s", [obligation.current_revision_id])
        raw = cursor.fetchone()[0]
    assert raw.startswith("pii:gcm:v1:") and "Private vendor" not in raw
    summary = json.loads(obligation.current_revision.decision_summary)
    assert summary["totals"]["approved_minor"] == 7000
    assert summary["lines"][0]["receipt"]["sha256"] == asset.sha256
    assert summary["eligibility"]["registration_id"] == claim.award.request.registration_id


def test_failed_core_evidence_creation_rolls_back_decision_and_budget(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    before = (claim.version, claim.current_decision_id)
    world.pool.refresh_from_db()
    counters = (world.pool.reserved_minor, world.pool.committed_minor, world.pool.version)
    # Fault injection is limited to the external seam; all prior writes are real.
    def fail(**kwargs):
        raise RuntimeError("injected core persistence failure")
    monkeypatch.setattr("apps.event_reimbursements.claim_decisions.preserve_locked", fail)
    with pytest.raises(RuntimeError):
        claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
            data=decision_data(world, claim, line_id, 10000))
    world.pool.refresh_from_db(); claim.refresh_from_db()
    assert (claim.version, claim.current_decision_id) == before
    assert (world.pool.reserved_minor, world.pool.committed_minor, world.pool.version) == counters
    assert not claim.decisions.exists()
    assert not EventPayoutObligation.objects.filter(source_uuid=claim.uuid).exists()
