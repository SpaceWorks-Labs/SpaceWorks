"""Lagging workers cannot extend offers; sweeps preserve submitted finance work."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.event_reimbursements import award_workflow, claim_workflow
from apps.event_reimbursements.models import GrantAward, ReimbursementClaim, ReimbursementWorkItem
from apps.event_reimbursements.tasks import sweep_one, sweep_deadlines_task
from apps.payments.event_payouts.errors import PayoutError
from .helpers import requested, accepted, submitted, decision_data
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_expired_offer_refuses_on_demand_and_releases_once(world, monkeypatch):
    grant = requested(world)
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
        data=cmd(grant.version, outcome="award", amount_minor=10000, currency="INR", reason_code="need_based",
            expected_award_version=None, expected_pool_version=world.pool.version))
    award = GrantAward.objects.get(request=grant)
    monkeypatch.setattr(timezone, "now", lambda: award.accept_by)
    with pytest.raises(PayoutError) as exc:
        award_workflow.respond(event_id=world.event.pk, actor=world.owner,
            data=cmd(award.version, award_revision=1), accept=True)
    assert exc.value.detail["code"] == "award_offer_closed"
    sweep_one(event_id=world.event.pk, award_id=award.pk)
    sweep_one(event_id=world.event.pk, award_id=award.pk)
    award.refresh_from_db(); world.pool.refresh_from_db()
    assert award.state == "expired" and world.pool.reserved_minor == 0
    assert world.pool.entries.filter(kind="release").count() == 1


def test_sweep_opens_claim_then_expires_no_receipts_once(world, monkeypatch):
    award = accepted(world)
    monkeypatch.setattr(timezone, "now", lambda: world.event.ends_at + timedelta(days=1))
    sweep_deadlines_task()
    claim = ReimbursementClaim.objects.get(award=award)
    assert claim.state == "open"
    monkeypatch.setattr(timezone, "now", lambda: claim.effective_due_at)
    sweep_deadlines_task(); sweep_deadlines_task()
    claim.refresh_from_db(); world.pool.refresh_from_db()
    assert claim.state == "expired" and claim.domain_closed_at is not None
    assert world.pool.reserved_minor == 0


def test_submitted_claim_never_expires_while_finance_is_reviewing(world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    monkeypatch.setattr(timezone, "now", lambda: claim.effective_due_at + timedelta(days=2))
    sweep_deadlines_task()
    claim.refresh_from_db(); world.pool.refresh_from_db()
    assert claim.state == "submitted" and claim.domain_closed_at is None
    assert world.pool.reserved_minor == 10000


def test_rejected_appeal_window_delays_domain_finality_and_closes_receipts(world, monkeypatch):
    claim, asset, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 0, outcome="rejected"))
    claim.refresh_from_db(); asset.refresh_from_db()
    assert claim.domain_closed_at is None and asset.terminal_financial_at is None
    monkeypatch.setattr(timezone, "now", lambda: claim.appeal_due_at)
    sweep_deadlines_task(); sweep_deadlines_task()
    claim.refresh_from_db(); asset.refresh_from_db()
    assert claim.domain_closed_at is not None and asset.terminal_financial_at is not None
    assert asset.closure_reason_code == "no_liability" and asset.expires_at > asset.terminal_financial_at


def test_extended_deadline_invalidates_old_work_and_reminder_identity(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    value = decision_data(world, claim, line_id, 0, outcome="returned_for_info")
    value.update(line_decisions=[], info_due_at=timezone.now() + timedelta(days=3))
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=value)
    claim.refresh_from_db()
    old_due = claim.info_due_at
    claim_workflow.extend(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=cmd(claim.version, due_revision=claim.due_revision, due_at=old_due + timedelta(days=5),
            reason_code="deadline_extension", note="Private extension explanation"))
    monkeypatch.setattr(timezone, "now", lambda: old_due + timedelta(seconds=1))
    sweep_deadlines_task()
    claim.refresh_from_db()
    assert claim.state == "returned_for_info" and claim.info_due_at > timezone.now()
