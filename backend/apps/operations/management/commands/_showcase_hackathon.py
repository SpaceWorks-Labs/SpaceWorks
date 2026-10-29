"""A running hackathon judged by pairwise comparison, for screenshots and the walkthrough.

Judging goes through its real workflows: the event through `create_event`, judge roles through
the staff role workflow (which grants their judging authority), the round through
`definitions_workflow` and `round_workflow`, and every comparison through `pairwise_workflow`,
so the audit trail, cursor versions and coverage are exactly what judges would produce.

The finished team projects are written as rows, like an imported history: the application, team
and submission workflows need live member sign-ins and file uploads, which a seed cannot make.
"""
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from . import _showcase_data as data


def _command(version=0, **fields):
    return {"operation_id": str(uuid4()), "expected_version": version, **fields}


def _project(event, leader, mate, index, title, description):
    from apps.events.hackathons.admission_models import HackathonApplication
    from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
    from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot
    from apps.events.submissions.pii import prepare_documents
    name = f"Team {title.split()[0]}"
    with prepare_documents(event.pk), transaction.atomic():
        team = HackathonTeam.objects.create(event=event, leader=leader, name=name, normalized_name=name.casefold())
        for member in (leader, mate):
            application = HackathonApplication.objects.create(event=event, member=member)
            HackathonTeamMember.objects.create(event=event, team=team, member=member, application=application,
                                               creator=leader, state="active")
        project = HackathonSubmission.objects.create(event=event, team=team, state="submitted", triage="eligible",
            title=title, description=description, submitted_at=timezone.now())
        snapshot = SubmissionSnapshot.objects.create(submission=project, sequence=1, submitted_by=leader,
            project={"title": title, "description": description}, content_sha256=f"{index + 1:064x}",
            sealed_member_ids=sorted((leader.pk, mate.pk)))
        project.current_snapshot = snapshot
        project.save(update_fields=["current_snapshot"])


def _judge(event, manager, member):
    from apps.events.contributions import management_workflow, role_workflow
    role = management_workflow.save_role(actor=manager, event_id=event.pk,
                                         payload=_command(member_id=member.pk, role="judge")).row
    role_workflow.transition(actor=manager, event_id=event.pk, assignment_id=role.pk,
                             payload=_command(role.version), action="approve")
    return role


def _judge_round(event, judge, round, comparisons):
    """View the first project, then compare `comparisons` times; the last project stays on screen."""
    from apps.events.judging import pairwise_workflow as workflow
    from apps.events.judging.models_pairwise import JudgePairwiseCursor

    def version():
        cursor = JudgePairwiseCursor.objects.filter(round=round, judge__member=judge).first()
        return cursor.version if cursor else 0
    workflow.next_project(event.pk, round.pk, actor=judge, data=_command(version()))
    for step in range(comparisons):
        outcome = "current" if step % 3 != 1 else "previous"
        workflow.compare(event.pk, round.pk, actor=judge, data=_command(version(), outcome=outcome))
        workflow.next_project(event.pk, round.pk, actor=judge, data=_command(version()))


def seed_hackathon(space, manager, members):
    from apps.events.hackathons.admission_models import HackathonConfig
    from apps.events.judging.definitions_workflow import save_definition
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.judging.round_workflow import transition
    from apps.events.services_event_details import create_event
    now = timezone.now()
    event = create_event(makerspace=space, actor=manager, title=data.HACKATHON["title"],
        description=data.HACKATHON["description"], starts_at=now - timedelta(hours=20),
        ends_at=now + timedelta(hours=4), location=data.LOCATION, capacity=40, is_public=True)
    HackathonConfig.objects.create(event=event, enabled=True, team_mode="team_together", team_max=2)
    for index, (leader, mate, title, description) in enumerate(data.HACKATHON["projects"]):
        _project(event, members[leader], members[mate], index, title, description)
    judges = [members[name] for name in data.HACKATHON["judges"]]
    for judge in judges:
        _judge(event, manager, judge)
    saved = save_definition(event.pk, actor=manager, kind="judging-rounds", data=_command(
        key="finals", mode="pairwise", min_reviews=3, guidance=data.HACKATHON["guidance"]))
    transition(event.pk, saved["id"], actor=manager, action="open", data=_command(saved["version"]))
    round = JudgingRound.objects.get(pk=saved["id"])
    # One judge has finished, one is midway and one has only seen a first project.
    for judge, comparisons in zip(judges, (len(data.HACKATHON["projects"]) - 1, 2, 0)):
        if comparisons:
            _judge_round(event, judge, round, comparisons)
    return event
