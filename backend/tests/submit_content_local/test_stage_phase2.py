"""#180 phase 2: released team feedback (S4), promote next (S12), push signal (S14), judge reminders (S15),
the stage funnel (S16) and early public stages (S18)."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.submissions import stage_integrity, stage_judge_reminders
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission
from apps.events.submissions.models_stages import (StageShortlist, StageShortlistAnnouncement, StageShortlistEntry,
                                                   SubmissionStageEntry)
from apps.events.submissions.stage_analytics import stage_funnel
from apps.events.submissions.stage_gallery import final_stage_entries, gallery_stage_allowed
from tests.events.collab_helpers import make_staff
from tests.submit_content_local.stage_helpers import REPO, run, save, stage, world

pytestmark = pytest.mark.django_db


def submitted(w, stage_row, teams):
    for index in range(teams):
        run(w, "submit", save(w, links=[REPO], team=index)["version"], {"stage_id": stage_row.pk}, team=index)
    return [HackathonSubmission.objects.get(team=t.team) for t in w.teams[:teams]]


def publish(w, stage_row, chosen, **values):
    row = StageShortlist.objects.create(event=w.event, stage=stage_row, fingerprint="f" * 64,
                                        **{"selection": "manual", **values})
    for project in chosen:
        StageShortlistEntry.objects.create(shortlist=row, submission=project, snapshot=project.current_snapshot)
    StageShortlistAnnouncement.objects.create(event=w.event, shortlist=row, published_at=timezone.now())
    return row


def test_the_funnel_counts_each_stage(monkeypatch):
    w = world(monkeypatch, teams=2)
    one, two = stage(w.event, 1, shortlist_after=True), stage(w.event, 2)
    projects = submitted(w, one, 2)
    SubmissionStageEntry.objects.update(triage="eligible")
    publish(w, one, projects[:1])
    run(w, "submit", projects[0].version, {"stage_id": two.pk})
    rows = stage_funnel(w.event)
    assert rows[0] == {"position": 1, "name": one.name, "submitted": 2, "eligible": 2, "shortlisted": 1, "advanced": 1}
    assert rows[1]["advanced"] is None and rows[1]["shortlisted"] is None


def test_an_early_stage_joins_the_gallery_only_when_public_and_only_for_passing_teams(monkeypatch):
    w = world(monkeypatch, teams=2)
    one = stage(w.event, 1, shortlist_after=True)
    stage(w.event, 2)
    projects = submitted(w, one, 2)
    snap = lambda project: SimpleNamespace(id=project.current_snapshot_id, stage_id=one.pk)
    assert not gallery_stage_allowed(w.event.pk, snap(projects[0]))  # Off by default.
    one.public_after_publish = True
    one.save()
    assert not gallery_stage_allowed(w.event.pk, snap(projects[0]))  # Not published yet.
    publish(w, one, projects[:1])
    assert gallery_stage_allowed(w.event.pk, snap(projects[0]))
    assert not gallery_stage_allowed(w.event.pk, snap(projects[1]))  # Eliminated: never.


def test_final_stage_entries_drop_early_stage_gallery_rows(monkeypatch):
    from apps.events.submissions.gallery_models import GalleryEntry
    w = world(monkeypatch)
    stage(w.event, 1)
    stage(w.event, 2)
    rows = final_stage_entries(w.event.pk, GalleryEntry.objects.filter(event=w.event))
    assert list(rows) == []


def test_promote_next_needs_a_withdrawn_shortlisted_team_and_a_ranked_source(monkeypatch):
    from apps.events.submissions.stage_promotion import promote_next
    w = world(monkeypatch, teams=2)
    manager = make_staff(w.event.makerspace, username=f"promoter-{uuid4().hex[:6]}")
    one = stage(w.event, 1, shortlist_after=True)
    stage(w.event, 2)
    projects = submitted(w, one, 2)
    publish(w, one, projects[:1])
    with pytest.raises(SubmissionError) as caught:
        promote_next(actor=manager, event_id=w.event.pk, stage_id=one.pk,
                     values={"operation_id": uuid4(), "withdrawn_submission_id": projects[0].pk})
    assert caught.value.detail["code"] == "not_a_withdrawn_shortlisted_team"
    run(w, "withdraw", HackathonSubmission.objects.get(pk=projects[0].pk).version)
    with pytest.raises(SubmissionError) as caught:
        promote_next(actor=manager, event_id=w.event.pk, stage_id=one.pk,
                     values={"operation_id": uuid4(), "withdrawn_submission_id": projects[0].pk})
    assert caught.value.detail["code"] == "no_ranked_source"  # A hand-picked list has no "next".


def test_a_promotion_is_a_published_amendment(monkeypatch):
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.submissions import stage_promotion
    w = world(monkeypatch, teams=2)
    manager = make_staff(w.event.makerspace, username=f"promoter-{uuid4().hex[:6]}")
    one = stage(w.event, 1, shortlist_after=True)
    stage(w.event, 2)
    projects = submitted(w, one, 2)
    SubmissionStageEntry.objects.update(triage="eligible")
    source = JudgingRound.objects.create(event=w.event, key="ideas", mode="top3", state="finalized", submission_stage=one)
    original = publish(w, one, projects[:1], selection="top_n", top_n=1, source_round=source)
    monkeypatch.setattr(stage_promotion, "_next_ranked", lambda current, keep: (
        [{"snapshot_id": projects[1].current_snapshot_id, "rank": 2}], {projects[1].current_snapshot_id: projects[1]}))
    run(w, "withdraw", HackathonSubmission.objects.get(pk=projects[0].pk).version)
    result = stage_promotion.promote_next(actor=manager, event_id=w.event.pk, stage_id=one.pk,
                                         values={"operation_id": uuid4(), "withdrawn_submission_id": projects[0].pk})
    assert result["current"]["selection"] == "promoted"
    assert [e["submission_id"] for e in result["current"]["entries"]] == [projects[1].pk]
    amendment = StageShortlist.objects.get(pk=result["current"]["id"])
    assert amendment.amends_id == original.pk and hasattr(amendment, "announcement")
    assert stage_promotion.promoted_recipients(amendment.announcement.pk) == (w.teams[1].user.pk,)
    assert AuditLog.objects.filter(action="event.submission_stage.shortlist_promoted").exists()


def test_judge_reminder_phases():
    now = timezone.now()
    open_round = SimpleNamespace(opens_at=now - timedelta(hours=10), closes_at=now + timedelta(hours=2))
    assert stage_judge_reminders.phases_due(open_round, now) == [1, 2, 3]
    early = SimpleNamespace(opens_at=now - timedelta(hours=1), closes_at=now + timedelta(days=3))
    assert stage_judge_reminders.phases_due(early, now) == [1]
    assert stage_judge_reminders.phases_due(SimpleNamespace(opens_at=None, closes_at=None), now) == [1]


def test_push_after_deadline_is_an_informational_flag():
    class Http:
        def __init__(self, response):
            self.response, self.urls = response, []

        def get_json(self, url, **kwargs):
            self.urls.append(url)
            return self.response
    deadline = timezone.now() - timedelta(hours=1)
    sha = "a" * 40
    http = Http([{"sha": sha}])
    evidence = stage_integrity.check_after(repo_url="https://github.com/acme/build", deadline=deadline, http=http)
    assert evidence == {"rule_key": "github_push_after_stage_deadline", "commit_sha": sha}
    assert "since=" in http.urls[0] and "api.github.com/repos/acme/build/commits" in http.urls[0]
    assert stage_integrity.check_after(repo_url="https://github.com/acme/build", deadline=deadline, http=Http([])) is None
    with pytest.raises(SubmissionError):
        stage_integrity.check_after(repo_url="https://github.com/acme/build", deadline=deadline, http=Http({"x": 1}))


def test_feedback_is_released_only_by_a_published_shortlist_or_result(monkeypatch):
    from apps.events.submissions import stage_feedback
    w = world(monkeypatch)
    one = stage(w.event, 1, shortlist_after=True)
    stage(w.event, 2)
    from apps.events.judging.models_definitions import JudgingRound
    round_row = JudgingRound.objects.create(event=w.event, key="ideas", mode="top3", state="finalized",
                                            submission_stage=one, share_feedback=True)
    assert not stage_feedback.released(round_row)
    publish(w, one, [])
    assert stage_feedback.released(round_row)
    round_row.share_feedback = False
    assert not stage_feedback.released(round_row)
    round_row.share_feedback, round_row.state = True, "open"
    assert not stage_feedback.released(round_row)
