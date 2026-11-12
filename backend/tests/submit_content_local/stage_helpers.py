"""Shared rows for the r2-submit-content tests (#177-#180).

The submission workflow runs through a small fake boundary (as in
tests/events/programme/submissions/test_snapshot_workflow.py): already-authorized inputs, real
models, real stage rules. Authority tests use the production ProgrammeBoundary instead.
"""
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.events.models import Event
from apps.events.submissions import ports
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_stages import SubmissionStage
from apps.events.submissions.ports import SubmissionContext
from apps.events.submissions.workflow import command
from tests.events.ticketing_helpers import account, event_space, open_event

GOOD = {"title": "A maker project", "ai_declaration": {"used": False, "details": ""},
        "reuse_declaration": {"used": False, "details": ""}}


class FakeBoundary:
    def __init__(self, event, teams):
        self.event, self.teams, self.receipts, self.invalidated = event, teams, {}, []

    @contextmanager
    def locked(self, *, actor=None, event_id=None, team_id=None, action=None):
        with transaction.atomic():
            locked = Event.objects.select_for_update().get(pk=self.event.pk)
            leader = self.teams[team_id].leader_id if team_id in self.teams else None
            members = (leader,) if leader else ()
            yield SubmissionContext(event=locked, team_id=team_id, member_ids=members, leader_id=leader,
                                    deadline=locked.ends_at, late_policy="reject")

    def receipt(self, *, event_id, actor_id, operation_id, digest):
        previous = self.receipts.get(str(operation_id))
        if previous and previous[0] != digest:
            raise SubmissionError("idempotency_conflict", 409)
        return previous[1] if previous else None

    def store_receipt(self, *, operation_id, digest, result, **kwargs):
        self.receipts[str(operation_id)] = (digest, result)

    def validate_project(self, **kwargs):
        return kwargs["project"]

    def lock_roster(self, **kwargs):
        pass

    def invalidate_snapshot(self, *, snapshot_id, **kwargs):
        self.invalidated.append(snapshot_id)


def team_for(event, name):
    user = account(f"{name}-{uuid4().hex[:8]}")
    with transaction.atomic():
        application = apps.get_model("events", "HackathonApplication").objects.create(event=event, member=user)
        team = apps.get_model("events", "HackathonTeam").objects.create(event=event, leader=user, name=name,
            normalized_name=name.lower())
        apps.get_model("events", "HackathonTeamMember").objects.create(event=event, team=team, member=user,
            application=application, creator=user, state="active")
    return SimpleNamespace(user=user, team=team)


def world(monkeypatch, *, teams=1, config=True):
    event = open_event(event_space(f"stages-{uuid4().hex[:8]}"))
    event.ends_at = timezone.now() + timedelta(days=10)
    event.save(update_fields=["ends_at"])
    if config:
        apps.get_model("events", "HackathonConfig").objects.create(event=event, enabled=True)
    rows = [team_for(event, f"team{index}") for index in range(teams)]
    boundary = FakeBoundary(event, {row.team.pk: row.team for row in rows})
    monkeypatch.setattr(ports, "_boundary", boundary)
    return SimpleNamespace(event=event, teams=rows, boundary=boundary)


def stage(event, position=1, **values):
    defaults = {"name": f"Stage {position}", "deadline": event.ends_at - timedelta(days=10 - 3 * position)}
    return SubmissionStage.objects.create(event=event, position=position, **{**defaults, **values})


def run(w, action, version, data=None, *, team=0, **kwargs):
    row = w.teams[team]
    return command(actor=row.user, event_id=w.event.pk, team_id=row.team.pk, action=action, expected_version=version,
                   data=data, operation_id=kwargs.pop("operation_id", str(uuid4())), **kwargs)


def save(w, version=0, *, links=(), team=0, **fields):
    data = {**GOOD, **fields}
    if links is not None:
        data["links"] = [{"kind": kind, "url": url, "public_requested": False} for kind, url in links]
    return run(w, "save", version, data, team=team)


REPO = ("repo", "https://github.com/example/project")
DEMO = ("demo", "https://example.com/demo")
VIDEO = ("video", "https://www.youtube.com/watch?v=abc")
