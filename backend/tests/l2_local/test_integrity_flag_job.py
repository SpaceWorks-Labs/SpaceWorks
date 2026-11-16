"""G10 GitHub first-commit flag (#8): information only, never disqualifies; GitHub fails safe."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.events.hackathons.admission_models import HackathonApplication, HackathonConfig
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.models_r2_l2 import SubmissionIntegrityCheck
from apps.events.submissions import integrity_jobs
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionIntegrityFlag, SubmissionSnapshot
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.l2_local.helpers import off, on

pytestmark = pytest.mark.django_db


def project(slug="integrity"):
    space = event_space(slug)
    staff = make_staff(space)
    user = account(f"{slug}-leader")
    event = open_event(space)
    event.starts_at = timezone.now() - timedelta(hours=1)
    event.save(update_fields=["starts_at"])
    HackathonConfig.objects.create(event=event, enabled=True)
    with transaction.atomic():
        application = HackathonApplication.objects.create(event=event, member=user)
        team = HackathonTeam.objects.create(event=event, leader=user, name="Makers")
        HackathonTeamMember.objects.create(event=event, team=team, member=user, application=application,
                                           creator=user, state="active")
        submission = HackathonSubmission.objects.create(event=event, team=team, state="submitted")
        snapshot = SubmissionSnapshot.objects.create(submission=submission, sequence=1, submitted_by=user,
                                                     project={"title": "Robot"}, content_sha256="a" * 64)
        HackathonSubmission.objects.filter(pk=submission.pk).update(current_snapshot=snapshot)
    on(space, "events.hackathons", "events.submission_integrity")
    return space, staff, event, submission, snapshot


def test_an_early_commit_flags_for_information_and_changes_nothing_else(monkeypatch):
    space, staff, event, submission, snapshot = project()
    monkeypatch.setattr(integrity_jobs, "_evidence", lambda snapshot, event: (
        "flagged", {"rule_key": "github_commit_before_kickoff", "commit_sha": "b" * 40}))
    assert integrity_jobs.sweep_space(space) == 1
    check = SubmissionIntegrityCheck.objects.get(snapshot=snapshot)
    assert check.state == "flagged"
    flag = SubmissionIntegrityFlag.objects.get(snapshot=snapshot)
    assert flag.severity == "informational"
    submission.refresh_from_db()
    assert submission.state == "submitted" and submission.triage == "pending"
    response = client_for(staff).get(f"/api/v1/admin/events/{event.pk}/submissions/{submission.pk}/integrity/")
    assert response.status_code == 200 and response.json()["check_state"] == "flagged"
    listed = client_for(staff).get(f"/api/v1/admin/events/{event.pk}/submissions/integrity/").json()
    assert listed["results"][0]["snapshot_id"] == snapshot.pk


def test_github_failure_fails_safe_and_gives_up_after_three_tries(monkeypatch):
    space, _staff, _event, _submission, snapshot = project("integrity-fail")

    def boom(snapshot, event):
        raise SubmissionError("integrity_provider_unavailable", 503)
    monkeypatch.setattr(integrity_jobs, "_evidence", boom)
    integrity_jobs.sweep_space(space)
    check = SubmissionIntegrityCheck.objects.get(snapshot=snapshot)
    assert check.state == "pending" and check.attempts == 1
    for _ in range(2):
        SubmissionIntegrityCheck.objects.filter(pk=check.pk).update(next_attempt_at=timezone.now())
        integrity_jobs.sweep_space(space)
    check.refresh_from_db()
    assert check.state == "unavailable" and not SubmissionIntegrityFlag.objects.exists()


def test_switch_off_means_no_job_and_a_404(monkeypatch):
    space, staff, event, submission, _snapshot = project("integrity-off")
    off(space, "events.submission_integrity")
    assert integrity_jobs.sweep_space(space) == 0
    url = f"/api/v1/admin/events/{event.pk}/submissions/{submission.pk}/integrity/"
    assert client_for(staff).get(url).status_code == 404


def test_evidence_without_a_repository_is_not_a_flag():
    class Links:
        def filter(self, **kwargs):
            return self

        def order_by(self, *args):
            return []
    state, evidence = integrity_jobs._evidence(SimpleNamespace(link_refs=Links()), SimpleNamespace())
    assert state == "no_repository" and evidence is None
