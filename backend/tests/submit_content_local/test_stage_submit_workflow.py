"""The stage-aware submit path (#177-#180) on real rows through a fake, already-authorized boundary."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot
from apps.events.submissions.models_stages import (SnapshotStage, StageExtension, StageShortlist,
                                                   StageShortlistAnnouncement, StageShortlistEntry, SubmissionStage,
                                                   SubmissionStageEntry)
from tests.submit_content_local.stage_helpers import DEMO, REPO, run, save, stage, world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w(monkeypatch):
    return world(monkeypatch)


def refused(call):
    with pytest.raises(SubmissionError) as caught:
        call()
    return caught.value.detail["code"], caught.value.detail


def test_an_event_without_stages_gets_the_single_submission_stage_and_behaves_as_before(w):
    saved = save(w, links=[REPO])
    first = run(w, "submit", saved["version"])
    only = SubmissionStage.objects.get(event=w.event)
    assert (only.position, only.name, only.content_mode) == (1, "Submission", "files_and_links")
    entry = SubmissionStageEntry.objects.get(stage=only)
    assert entry.current_snapshot_id == first["snapshot_id"] == HackathonSubmission.objects.get().current_snapshot_id
    assert SnapshotStage.objects.get(snapshot_id=first["snapshot_id"]).stage_id == only.pk
    again = run(w, "submit", run(w, "save", first["version"], {"title": "Revised"})["version"])
    assert w.boundary.invalidated == [first["snapshot_id"]] and again["snapshot_id"] != first["snapshot_id"]


def test_files_only_refuses_links_in_a_draft_and_at_submit(w):
    stage(w.event, content_mode="files_only")
    assert refused(lambda: save(w, links=[REPO]))[0] == "submission_links_disabled"
    draft = save(w, links=None)["version"]  # A draft may be incomplete: no files yet is fine.
    assert refused(lambda: run(w, "submit", draft))[0] == "submission_content_required"


def test_links_only_refuses_files_in_a_draft(w):
    stage(w.event, content_mode="links_only")
    assert refused(lambda: save(w, links=[REPO], asset_ids=[1]))[0] == "submission_files_disabled"


def test_required_link_kind_is_enforced_at_submit_not_in_the_draft(w):
    stage(w.event, required_link_kinds=["repo"])
    saved = save(w, links=[DEMO])  # Incomplete drafts are allowed.
    name, body = refused(lambda: run(w, "submit", saved["version"]))
    assert name == "submission_link_required" and list(body["kinds"]) == ["repo"]
    fixed = run(w, "save", saved["version"], {"links": [{"kind": "repo", "url": REPO[1], "public_requested": False}]})
    assert run(w, "submit", fixed["version"])["snapshot_id"]


def test_min_files_and_max_links_are_enforced_at_submit(w):
    stage(w.event, min_files=1, max_links=1)
    saved = save(w, links=[REPO, DEMO])
    assert refused(lambda: run(w, "submit", saved["version"]))[0] == "submission_files_required"
    row = SubmissionStage.objects.get(event=w.event)
    row.min_files = 0
    row.save()
    name, body = refused(lambda: run(w, "submit", saved["version"]))
    assert name == "submission_too_many_links" and body["limit"] == "1"


def test_changing_the_setting_never_touches_a_submitted_snapshot(w):
    row = stage(w.event)
    first = run(w, "submit", save(w, links=[DEMO])["version"])
    frozen = SubmissionSnapshot.objects.get(pk=first["snapshot_id"]).project
    row.required_link_kinds, row.version = ["repo"], row.version + 1
    row.save()
    after = SubmissionSnapshot.objects.get(pk=first["snapshot_id"]).project
    assert after == frozen and after["stage"]["rules"]["required_link_kinds"] == []
    assert refused(lambda: run(w, "submit", first["version"]))[0] == "submission_link_required"  # The next submit.


def test_resubmission_once_refuses_a_second_submit(w):
    stage(w.event, resubmission="once")
    first = run(w, "submit", save(w, links=[REPO])["version"])
    assert refused(lambda: run(w, "submit", first["version"]))[0] == "stage_already_submitted"


def test_later_stage_needs_the_previous_one_and_its_opening(w):
    one = stage(w.event, 1)
    two = stage(w.event, 2, requires_previous=True)
    saved = save(w, links=[REPO])
    name, _ = refused(lambda: run(w, "submit", saved["version"], {"stage_id": two.pk}))
    assert name == "previous_stage_required"
    first = run(w, "submit", saved["version"], {"stage_id": one.pk})
    two.opens_at = timezone.now() + timedelta(hours=1)
    two.save()
    assert refused(lambda: run(w, "submit", first["version"], {"stage_id": two.pk}))[0] == "stage_not_open"


def test_each_stage_keeps_its_own_current_snapshot(w):
    one, two = stage(w.event, 1), stage(w.event, 2)
    first = run(w, "submit", save(w, links=[REPO])["version"], {"stage_id": one.pk})
    second = run(w, "submit", first["version"], {"stage_id": two.pk})
    third = run(w, "submit", second["version"], {"stage_id": two.pk})
    assert w.boundary.invalidated == [second["snapshot_id"]]  # Stage 1's work is never superseded by stage 2.
    entries = {e.stage_id: e.current_snapshot_id for e in SubmissionStageEntry.objects.all()}
    assert entries == {one.pk: first["snapshot_id"], two.pk: third["snapshot_id"]}
    assert HackathonSubmission.objects.get().current_snapshot_id == third["snapshot_id"]  # The furthest stage.


def shortlist(w, stage_row, chosen, *, publish=True):
    row = StageShortlist.objects.create(event=w.event, stage=stage_row, selection="manual", fingerprint="x" * 64)
    for project in chosen:
        StageShortlistEntry.objects.create(shortlist=row, submission=project, snapshot=project.current_snapshot)
    if publish:
        StageShortlistAnnouncement.objects.create(event=w.event, shortlist=row, published_at=timezone.now())
    return row


def test_shortlist_gate_opens_the_next_stage_only_to_chosen_teams(monkeypatch):
    w = world(monkeypatch, teams=2)
    one = stage(w.event, 1, shortlist_after=True)
    two = stage(w.event, 2)
    versions = [run(w, "submit", save(w, links=[REPO], team=i)["version"], {"stage_id": one.pk}, team=i)["version"]
                for i in range(2)]
    assert refused(lambda: run(w, "submit", versions[0], {"stage_id": two.pk}))[0] == "shortlist_pending"
    chosen = HackathonSubmission.objects.get(team=w.teams[0].team)
    shortlist(w, one, [chosen])
    assert run(w, "submit", versions[0], {"stage_id": two.pk})["snapshot_id"]
    name, _ = refused(lambda: run(w, "submit", versions[1], {"stage_id": two.pk}, team=1))
    assert name == "not_shortlisted"
    loser = HackathonSubmission.objects.get(team=w.teams[1].team)
    assert SubmissionStageEntry.objects.get(submission=loser, stage=one).current_snapshot_id  # Keeps earlier work.
    assert refused(lambda: run(w, "submit", versions[1], {"stage_id": one.pk}, team=1))[0] == "stage_closed"


def test_an_extension_lets_one_team_submit_late_and_marks_it(w):
    row = stage(w.event, deadline=timezone.now() + timedelta(hours=1))
    saved = save(w, links=[REPO])  # Drafting ends at the last stage's cutoff, so the draft is saved first.
    SubmissionStage.objects.filter(pk=row.pk).update(deadline=timezone.now() - timedelta(minutes=5))
    assert refused(lambda: run(w, "submit", saved["version"], {"stage_id": row.pk}))[0] == "submission_deadline"
    extension = StageExtension.objects.create(stage=row, team=w.teams[0].team, until=timezone.now() + timedelta(hours=1),
                                              reason="Power cut")
    done = run(w, "submit", saved["version"], {"stage_id": row.pk})
    snapshot = SubmissionSnapshot.objects.get(pk=done["snapshot_id"])
    assert snapshot.late and SnapshotStage.objects.get(snapshot=snapshot).extension_id == extension.pk


def test_late_policy_is_per_stage(w):
    row = stage(w.event, deadline=timezone.now() + timedelta(hours=1), late_policy="accept_flagged")
    saved = save(w, links=[REPO])  # The draft lock still ends drafting; the late policy only governs submit.
    SubmissionStage.objects.filter(pk=row.pk).update(deadline=timezone.now() - timedelta(minutes=5))
    done = run(w, "submit", saved["version"], {"stage_id": row.pk})
    assert SubmissionSnapshot.objects.get(pk=done["snapshot_id"]).late


def test_custom_answers_save_in_the_draft_and_freeze_at_submit(w):
    row = stage(w.event, custom_fields=[{"key": "problem", "label": "Problem", "type": "long_text", "required": True,
                                         "visible_to": "public"}])
    saved = save(w, links=[REPO])
    assert refused(lambda: run(w, "submit", saved["version"]))[0] == "submission_field_required"
    answered = run(w, "save", saved["version"], {"form_answers": {f"stage:{row.pk}": {"problem": "Flooding"}}})
    done = run(w, "submit", answered["version"])
    frozen = SubmissionSnapshot.objects.get(pk=done["snapshot_id"]).project["stage"]
    assert frozen["answers"] == {"problem": "Flooding"} and frozen["custom_fields"][0]["visible_to"] == "public"


def test_withdrawal_invalidates_every_stage(w):
    one, two = stage(w.event, 1), stage(w.event, 2)
    first = run(w, "submit", save(w, links=[REPO])["version"], {"stage_id": one.pk})
    second = run(w, "submit", first["version"], {"stage_id": two.pk})
    run(w, "withdraw", second["version"])
    assert set(w.boundary.invalidated) >= {first["snapshot_id"], second["snapshot_id"]}
