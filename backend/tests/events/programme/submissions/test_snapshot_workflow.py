"""Real-DB B workflow tests; G must install A/B models and guard SQL first.

This boundary fixture provides already-authorized domain inputs only. Integrated
source/PII/host/eligibility concurrency belongs to G's real composed adapters.
"""
from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import transaction, DatabaseError
from django.utils import timezone

from apps.events.models import Event
from apps.events.submissions import ports
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot
from apps.events.submissions.ports import SubmissionContext
from apps.events.submissions.workflow import command
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


@pytest.fixture
def domain(monkeypatch):
    user = account("maker-submission")
    event = open_event(event_space("maker-submissions"))
    team_model = apps.get_model("events", "HackathonTeam")
    with transaction.atomic():
        application = apps.get_model("events", "HackathonApplication").objects.create(event=event, member=user)
        team = team_model.objects.create(event=event, leader=user, name="Workshop team")
        apps.get_model("events", "HackathonTeamMember").objects.create(event=event, team=team, member=user,
            application=application, creator=user, state="active")
    receipts, invalidated = {}, []
    class Boundary:
        @contextmanager
        def locked(self, **kwargs):
            with transaction.atomic():
                locked = Event.objects.select_for_update().get(pk=event.pk)
                yield SubmissionContext(event=locked, team_id=team.pk, member_ids=(user.pk,), leader_id=user.pk,
                    deadline=event.ends_at, late_policy="reject")
        def receipt(self, *, event_id, actor_id, operation_id, digest):
            previous = receipts.get(str(operation_id))
            if previous and previous[0] != digest:
                raise SubmissionError("idempotency_conflict", 409)
            return previous[1] if previous else None
        def store_receipt(self, *, operation_id, digest, result, **kwargs):
            receipts[str(operation_id)] = (digest, result)
        def validate_project(self, **kwargs):
            return kwargs["project"]
        def lock_roster(self, **kwargs):
            pass
        def invalidate_snapshot(self, *, snapshot_id, **kwargs):
            invalidated.append(snapshot_id)
    monkeypatch.setattr(ports, "_boundary", Boundary())
    return user, event, team, invalidated


def execute(domain, action, version, data=None, **kwargs):
    user, event, team, _ = domain
    return command(actor=user, event_id=event.pk, team_id=team.pk, action=action,
        expected_version=version, data=data, operation_id=kwargs.pop("operation_id", str(uuid4())), **kwargs)


def draft(domain):
    return execute(domain, "save", 0, {"title": "A maker project", "ai_declaration": {"used": False, "details": ""},
        "reuse_declaration": {"used": False, "details": ""}, "links": [
            {"kind": "repo", "url": "https://github.com/example/project", "public_requested": False}]})


def test_resubmit_appends_snapshot_and_invalidates_superseded_scores(domain):
    saved = draft(domain)
    first = execute(domain, "submit", saved["version"])
    modified = execute(domain, "save", first["version"], {"title": "A revised maker project"})
    second = execute(domain, "submit", modified["version"])
    assert first["snapshot_id"] != second["snapshot_id"]
    old = SubmissionSnapshot.objects.get(pk=first["snapshot_id"])
    assert old.project["title"] == "A maker project" and old.sequence == 1
    assert SubmissionSnapshot.objects.get(pk=second["snapshot_id"]).sequence == 2
    assert domain[3] == [first["snapshot_id"]]


def test_replay_is_identical_and_changed_digest_is_conflict(domain):
    saved = draft(domain)
    operation_id = str(uuid4())
    first = execute(domain, "submit", saved["version"], operation_id=operation_id)
    assert execute(domain, "submit", saved["version"], operation_id=operation_id) == first
    assert SubmissionSnapshot.objects.count() == 1
    with pytest.raises(SubmissionError, match="idempotency_conflict"):
        execute(domain, "submit", saved["version"] + 1, operation_id=operation_id)


def test_worker_lateness_cannot_replace_last_snapshot_with_draft(domain):
    saved = draft(domain)
    first = execute(domain, "submit", saved["version"])
    edited = execute(domain, "save", first["version"], {"title": "Unfinished draft"})
    with pytest.raises(SubmissionError, match="submission deadline"):
        execute(domain, "submit", edited["version"], now=domain[1].ends_at + timedelta(microseconds=1))
    assert HackathonSubmission.objects.get().current_snapshot_id == first["snapshot_id"]


def test_database_bulk_update_cannot_mutate_frozen_history(domain):
    saved = draft(domain)
    first = execute(domain, "submit", saved["version"])
    with pytest.raises(DatabaseError), transaction.atomic():
        SubmissionSnapshot.objects.filter(pk=first["snapshot_id"]).update(project={"title": "tampered"})
