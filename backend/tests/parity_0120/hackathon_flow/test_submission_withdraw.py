"""Decision 296 review: only the team leader withdraws the team's submission, and never over a disqualification."""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from django.db import transaction

from apps.events.models import Event
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission
from apps.events.submissions.ports import SubmissionContext
from apps.events.submissions.workflow import command
from tests.events.ticketing_helpers import account
from tests.submit_content_local.stage_helpers import run, save, world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w(monkeypatch):
    row = world(monkeypatch, teams=1)
    row.member = account(f"teammate-{uuid4().hex[:8]}")
    boundary, leader = row.boundary, row.teams[0].user

    @contextmanager
    def locked(*, actor=None, event_id=None, team_id=None, action=None):
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=row.event.pk)
            yield SubmissionContext(event=event, team_id=team_id, member_ids=(leader.pk, row.member.pk),
                                    leader_id=leader.pk, deadline=event.ends_at, late_policy="reject")
    boundary.locked = locked
    return row


def withdraw_as(w, actor, version):
    return command(actor=actor, event_id=w.event.pk, team_id=w.teams[0].team.pk, action="withdraw",
                   expected_version=version, data=None, operation_id=str(uuid4()))


def refused(call):
    with pytest.raises(SubmissionError) as caught:
        call()
    return caught.value.detail["code"]


def test_a_team_member_who_is_not_the_leader_cannot_withdraw(w):
    version = save(w)["version"]
    assert refused(lambda: withdraw_as(w, w.member, version)) == "leader_required"
    assert HackathonSubmission.objects.get(team=w.teams[0].team).state == "draft"


def test_the_leader_withdraws(w):
    version = save(w)["version"]
    assert run(w, "withdraw", version)["state"] == "withdrawn"


def test_a_disqualified_project_cannot_be_withdrawn_over_the_decision(w):
    save(w)
    project = HackathonSubmission.objects.get(team=w.teams[0].team)
    HackathonSubmission.objects.filter(pk=project.pk).update(state="disqualified")
    assert refused(lambda: run(w, "withdraw", project.version)) == "invalid_transition"
