"""Finance finality, returned information, corrections and funded appeals."""
from datetime import timedelta
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.event_reimbursements import claim_workflow
from apps.event_reimbursements.budget_models import BudgetReservation
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.validation import PayoutValidationError
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from .conftest import cmd
from .helpers import submitted, decision_data

pytestmark = pytest.mark.django_db(transaction=True)


def test_partial_appeal_reacquires_released_funds_once(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 6000, outcome="partially_approved"))
    claim.refresh_from_db()
    value = cmd(claim.version, current_revision=claim.current_revision_id, statement="Private appeal evidence")
    result = claim_workflow.appeal(event_id=world.event.pk, actor=world.owner, request=world.member_session, data=value)
    assert claim_workflow.appeal(event_id=world.event.pk, actor=world.owner, request=world.member_session, data=value) == result
    world.pool.refresh_from_db(); claim.refresh_from_db()
    assert (world.pool.reserved_minor, world.pool.committed_minor) == (4000, 6000)
    assert claim.appeal_used and claim.state == "under_review"
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    assert obligation.eligibility_status == "held"
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 10000))
    claim.refresh_from_db(); obligation.refresh_from_db(); world.pool.refresh_from_db()
    assert claim.domain_closed_at is not None and claim.appeal.resolved_decision_id == claim.current_decision_id
    assert obligation.approved_minor == 10000 and obligation.revisions.count() == 2
    assert (world.pool.reserved_minor, world.pool.committed_minor) == (0, 10000)
    assert EventPayoutObligation.objects.filter(source_uuid=claim.uuid).count() == 1


def test_exhausted_appeal_budget_rolls_back_appeal_and_hold(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 6000, outcome="partially_approved"))
    from apps.event_reimbursements import programme_workflow
    world.programme.refresh_from_db(); world.pool.refresh_from_db()
    programme_workflow.configure(request=world.finance, event_id=world.event.pk,
        data=cmd(world.programme.version, policy_revision=world.programme.finance_policy_revision, settings={},
            pool_id=world.pool.pk, expected_pool_version=world.pool.version, budget_delta_minor=-(world.pool.total_minor - 6000),
            reason_code="other"))
    claim.refresh_from_db()
    with pytest.raises((PayoutError, PayoutValidationError)) as exc:
        claim_workflow.appeal(event_id=world.event.pk, actor=world.owner, request=world.member_session,
            data=cmd(claim.version, current_revision=claim.current_revision_id, statement="Appeal"))
    assert exc.value.code == "budget_exhausted" if isinstance(exc.value, PayoutValidationError) else exc.value.detail["code"] == "budget_exhausted"
    claim.refresh_from_db()
    assert not claim.appeal_used and not hasattr(claim, "appeal")


def test_returned_info_preserves_hold_and_resubmit_appends_revision(world, monkeypatch):
    claim, asset, line_id = submitted(world, monkeypatch)
    value = decision_data(world, claim, line_id, 0, outcome="returned_for_info")
    value.update(line_decisions=[], info_due_at=timezone.now() + timedelta(days=5))
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=value)
    claim.refresh_from_db(); world.pool.refresh_from_db()
    assert claim.state == "returned_for_info" and world.pool.reserved_minor == 10000
    claim_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session,
        data=cmd(claim.version, current_revision=claim.current_revision_id))
    claim.refresh_from_db()
    assert claim.state == "submitted" and claim.revisions.count() == 2
    assert claim.revisions.get(revision=1).lines.get().finance_asset_id == asset.pk


def test_correct_unpaid_decision_preserves_one_obligation_and_original(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 6000, outcome="partially_approved"))
    original = claim.decisions.get()
    value = decision_data(world, claim, line_id, 5000, outcome="partially_approved")
    value.pop("mode")
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=value, correction=True)
    original.refresh_from_db(); world.pool.refresh_from_db()
    assert original.approved_total_minor == 6000
    assert world.pool.committed_minor == 5000
    assert claim.decisions.count() == 2 and EventPayoutObligation.objects.filter(source_uuid=claim.uuid).count() == 1
