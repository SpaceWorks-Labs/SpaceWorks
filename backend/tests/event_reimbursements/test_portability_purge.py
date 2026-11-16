"""Terminal domain purge preserves the ledger and refuses pending review work."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.event_reimbursements import claim_workflow
from apps.event_reimbursements.purge import preflight
from apps.event_reimbursements.tasks import sweep_deadlines_task
from apps.event_reimbursements.models import ReimbursementProgramme, GrantAward
from apps.event_reimbursements.object_capture import module_private_keys
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from .helpers import submitted, accepted, decision_data

pytestmark = pytest.mark.django_db(transaction=True)


def test_purge_preflight_refuses_accepted_award_and_unfinished_claim(world, monkeypatch):
    claim, asset, _ = submitted(world, monkeypatch)
    value = preflight(world.space.pk)
    assert not value["allowed"]
    blockers = {row["code"]: row["count"] for row in value["blockers"]}
    assert blockers["unfinished_reimbursement_awards"] == 1
    assert blockers["unfinished_reimbursement_claims"] == 1
    assert value["preserved_finance_attachments"] == 1


@pytest.mark.parametrize("module", ["events", "event_reimbursements"])
def test_actual_module_purge_preserves_terminal_unpaid_liability(world, monkeypatch, module):
    claim, asset, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 10000))
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    assert preflight(world.space.pk)["allowed"]
    from apps.makerspaces.module_purge import purge_module
    from apps.accounts.models import User
    actor = User.objects.create_superuser(username="purge-owner", password="Purge test password 491!")
    world.space.enabled_modules = [key for key in world.space.enabled_modules if key != module]
    world.space.save(update_fields=["enabled_modules"])
    purge_module(world.space, module, actor)
    obligation.refresh_from_db(); asset.refresh_from_db()
    assert obligation.approved_minor == 10000 and obligation.domain_coordination_state == "detached"
    assert obligation.current_revision.decision_summary
    assert asset.obligation_id == obligation.pk
    assert not ReimbursementProgramme.objects.filter(event_id=world.event.pk).exists()


def test_partial_appeal_window_blocks_both_purges_until_workflow_finalizes(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 7000, outcome="partially_approved"))
    assert not preflight(world.space.pk)["allowed"]
    claim.refresh_from_db()
    monkeypatch.setattr(timezone, "now", lambda: claim.appeal_due_at + timedelta(seconds=1))
    sweep_deadlines_task()
    assert preflight(world.space.pk)["allowed"]
    assert tuple(module_private_keys(world.space)) == ()


def test_no_liability_receipt_missing_closure_blocks_purge(world, monkeypatch):
    claim, asset, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 0, outcome="rejected"))
    claim.refresh_from_db()
    monkeypatch.setattr(timezone, "now", lambda: claim.appeal_due_at + timedelta(seconds=1))
    sweep_deadlines_task()
    assert preflight(world.space.pk)["allowed"]
    # Simulate imported/corrupted metadata without manufacturing a new liability.
    FinanceAttachment.objects.filter(pk=asset.pk).update(closure_operation_id=None)
    value = preflight(world.space.pk)
    assert not value["allowed"]
    assert any(b["code"] == "missing_finance_attachment_closure" for b in value["blockers"])
