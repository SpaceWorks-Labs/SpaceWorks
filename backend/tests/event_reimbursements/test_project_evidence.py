"""Optional project policy consumes only B's current frozen accepted snapshot."""
import pytest
from django.db import transaction
from apps.events.models import HackathonTeam, HackathonTeamMember, HackathonSubmission, SubmissionSnapshot
from apps.event_reimbursements.eligibility import canonical_project
from apps.event_reimbursements import programme_workflow, claim_workflow
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from .helpers import accepted, submitted, decision_data
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_hackathon_optional_project_provenance_is_preserved_in_decision(make_world, monkeypatch):
    world = make_world(hackathon=True)
    programme_workflow.configure(request=world.finance, event_id=world.event.pk,
        data=cmd(world.programme.version, policy_revision=world.programme.finance_policy_revision,
            settings={"require_project_submission": True}, pool_id=world.pool.pk,
            expected_pool_version=world.pool.version, budget_delta_minor=0, reason_code="approved"))
    world.programme.refresh_from_db(); world.pool.refresh_from_db()
    award = accepted(world)
    # Solo admission already seats the owner on an active team; otherwise the team and its
    # active leader commit together (deferred leader guard).
    seat = HackathonTeamMember.objects.filter(event=world.event, member=world.owner, state="active").first()
    if seat is not None:
        team = seat.team
    else:
        with transaction.atomic():
            team = HackathonTeam.objects.create(event=world.event, leader=world.owner, name="Project team", normalized_name="project-team")
            HackathonTeamMember.objects.create(event=world.event, team=team, application=award.request.application,
                member=world.owner, creator=world.owner, state="active")
    project = HackathonSubmission.objects.create(event=world.event, team=team, state="submitted", triage="eligible")
    snapshot = SubmissionSnapshot.objects.create(submission=project, sequence=1, submitted_by=world.owner,
        sealed_member_ids=[world.owner.pk], project={"title": "Frozen project"}, content_sha256="f" * 64)
    project.current_snapshot = snapshot
    project.save(update_fields=["current_snapshot"])
    proof = canonical_project(event=world.event, owner_id=world.owner.pk)
    assert proof.snapshot_id == snapshot.pk
    assert canonical_project(event=world.event, owner_id=world.manager.pk) is None
    claim, _, line_id = submitted(world, monkeypatch, award=award)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 10000))
    claim.refresh_from_db()
    assert claim.current_decision.project_snapshot_ref == proof.reference
    import json
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    assert json.loads(obligation.current_revision.decision_summary)["eligibility"]["project_snapshot_ref"] == str(proof.reference)
