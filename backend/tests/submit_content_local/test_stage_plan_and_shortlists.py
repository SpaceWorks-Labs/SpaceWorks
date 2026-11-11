"""The organiser's stage editor and shortlist gates (#178, #179, #180 S2/S5/S11) through the fake boundary."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.apps import apps
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.judging.models_options import HackathonProgrammeOptions
from apps.events.judging.models_results import JudgingNotice
from apps.events.submissions import stage_service, stage_shortlists, stage_staff
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission
from apps.events.submissions.models_stages import (StageExtension, StageShortlistAnnouncement, SubmissionStage,
                                                   SubmissionStageEntry)
from apps.events.submissions.stage_service import fingerprint
from tests.events.collab_helpers import make_staff
from tests.submit_content_local.stage_helpers import REPO, run, save, stage, world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w(monkeypatch):
    row = world(monkeypatch, teams=2)
    row.manager = make_staff(row.event.makerspace, username=f"stage-manager-{uuid4().hex[:6]}")
    return row


def refused(call):
    with pytest.raises(SubmissionError) as caught:
        call()
    return caught.value.detail["code"], caught.value.detail


def replace(w, stages, *, expected=None, preset=""):
    current = list(SubmissionStage.objects.filter(event=w.event).order_by("position"))
    return stage_service.replace(actor=w.manager, event_id=w.event.pk, data={
        "operation_id": uuid4(), "expected_fingerprint": fingerprint(current) if expected is None else expected,
        "preset": preset, "stages": stages})


def row(name, days, **values):
    return {"name": name, "deadline": timezone.now() + timedelta(days=days), **values}


def test_a_preset_plan_replaces_the_single_stage_mirrors_the_window_and_is_audited(w):
    result = replace(w, [row("Idea", 1, shortlist_after=True), row("Prototype", 2), row("Final", 3)],
                     preset="idea_prototype_final")
    assert [s["name"] for s in result["stages"]] == ["Idea", "Prototype", "Final"]
    config = apps.get_model("events", "HackathonConfig").objects.get(event=w.event)
    assert config.submission_deadline == SubmissionStage.objects.get(event=w.event, position=3).deadline
    log = AuditLog.objects.filter(action="event.submission_stages.updated").latest("pk")
    assert log.meta["preset"] == "idea_prototype_final" and log.meta["created"] == 3


def test_a_stale_fingerprint_is_refused(w):
    replace(w, [row("One", 1)])
    assert refused(lambda: replace(w, [row("Two", 1)], expected="0" * 64))[0] == "stale_version"


def test_reorder_keeps_ids_and_a_used_stage_cannot_be_removed(w):
    first = replace(w, [row("A", 1), row("B", 2)])
    a, b = (s["id"] for s in first["stages"])
    swapped = replace(w, [{"id": b, **row("B", 1)}, {"id": a, **row("A", 2)}])
    assert [s["id"] for s in swapped["stages"]] == [b, a]
    run(w, "submit", save(w, links=[REPO])["version"], {"stage_id": b})
    assert refused(lambda: replace(w, [{"id": a, **row("A", 2)}]))[0] == "stage_in_use"


def test_editing_a_used_stage_is_allowed_and_bumps_its_version(w):
    plan = replace(w, [row("Only", 1)])
    only = plan["stages"][0]
    run(w, "submit", save(w, links=[REPO])["version"])
    edited = replace(w, [{"id": only["id"], **row("Only", 1, required_link_kinds=["repo"])}])
    assert edited["stages"][0]["version"] == only["version"] + 1


def test_the_config_window_writes_through_one_stage_and_is_refused_with_several(w):
    from apps.events.submissions.stage_config import refuse_multi_stage
    config = apps.get_model("events", "HackathonConfig").objects.get(event=w.event)
    refuse_multi_stage(config, {"submission_deadline": timezone.now()})  # One (virtual) stage: allowed.
    replace(w, [row("A", 1), row("B", 2)])
    config.refresh_from_db()
    with pytest.raises(Exception) as caught:
        refuse_multi_stage(config, {"submission_deadline": config.submission_deadline + timedelta(hours=1)})
    assert "submission_window_by_stage" in str(caught.value.detail)


def submit_both(w, stage_row):
    for index in range(2):
        run(w, "submit", save(w, links=[REPO], team=index)["version"], {"stage_id": stage_row.pk}, team=index)
    return [HackathonSubmission.objects.get(team=t.team) for t in w.teams]


def test_a_shortlist_waits_for_triage_then_applies_and_publishes_once(w):
    one, two = stage(w.event, 1, shortlist_after=True, shortlist_label="Shortlist"), stage(w.event, 2)
    projects = submit_both(w, one)
    values = {"selection": "manual", "submission_ids": [projects[0].pk]}
    name, body = refused(lambda: stage_shortlists.preview(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values=values))
    assert name == "triage_pending" and body["limit"] == "2"
    stage_staff.bulk_triage(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values={
        "operation_id": uuid4(), "submission_ids": [p.pk for p in projects], "triage": "eligible", "reason": "Checked"})
    plan = stage_shortlists.preview(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values=values)
    assert (plan["candidates"], plan["not_shortlisted"], plan["email_enabled"]) == (2, 1, False)  # S11: off by default.
    applied = stage_shortlists.apply(actor=w.manager, event_id=w.event.pk, stage_id=one.pk,
                                     values={**values, "operation_id": uuid4(), "fingerprint": plan["fingerprint"]})
    assert applied["allowed_actions"] == ["apply", "publish"]
    published = stage_shortlists.publish(actor=w.manager, event_id=w.event.pk, stage_id=one.pk,
                                         values={"operation_id": uuid4(), "shortlist_id": applied["current"]["id"]})
    assert published["current"]["published_at"] and published["allowed_actions"] == []
    assert not JudgingNotice.objects.filter(kind__startswith="stage_").exists()  # The email switch is off.
    assert refused(lambda: stage_shortlists.publish(actor=w.manager, event_id=w.event.pk, stage_id=one.pk,
        values={"operation_id": uuid4(), "shortlist_id": applied["current"]["id"]}))[0] == "shortlist_published"
    assert AuditLog.objects.filter(action="event.submission_stage.shortlist_published").exists()
    assert two.pk  # The next stage now opens to the shortlisted team only (see the workflow tests).


def test_a_changed_plan_is_refused_and_the_switch_sends_both_notices(w):
    one = stage(w.event, 1, shortlist_after=True)
    stage(w.event, 2)
    projects = submit_both(w, one)
    SubmissionStageEntry.objects.filter(stage=one).update(triage="eligible")
    HackathonProgrammeOptions.objects.create(event=w.event, shortlist_email=True)
    values = {"selection": "manual", "submission_ids": [projects[1].pk]}
    plan = stage_shortlists.preview(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values=values)
    assert refused(lambda: stage_shortlists.apply(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values={
        **values, "operation_id": uuid4(), "fingerprint": "f" * 64}))[0] == "plan_changed"
    applied = stage_shortlists.apply(actor=w.manager, event_id=w.event.pk, stage_id=one.pk,
                                     values={**values, "operation_id": uuid4(), "fingerprint": plan["fingerprint"]})
    stage_shortlists.publish(actor=w.manager, event_id=w.event.pk, stage_id=one.pk,
                             values={"operation_id": uuid4(), "shortlist_id": applied["current"]["id"]})
    kinds = set(JudgingNotice.objects.values_list("kind", flat=True))
    assert {"stage_shortlisted", "stage_not_shortlisted"} <= kinds
    announcement = StageShortlistAnnouncement.objects.get()
    chosen = stage_shortlists.recipients("stage_shortlisted", announcement.pk)
    others = stage_shortlists.recipients("stage_not_shortlisted", announcement.pk)
    assert chosen == (w.teams[1].user.pk,) and others == (w.teams[0].user.pk,)


def test_a_stage_without_a_gate_has_no_shortlist(w):
    plain = stage(w.event, 1)
    assert refused(lambda: stage_shortlists.read(actor=w.manager, event_id=w.event.pk, stage_id=plain.pk))[0] \
        == "shortlist_not_enabled"


def test_an_extension_is_append_only_audited_and_bounded_by_the_event(w):
    one = stage(w.event, 1)
    team = w.teams[0].team
    granted = stage_staff.extend(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values={
        "operation_id": uuid4(), "team_id": team.pk, "until": one.deadline + timedelta(hours=2), "reason": "Medical"})
    assert StageExtension.objects.get(pk=granted["id"]).created_by_id == w.manager.pk
    assert AuditLog.objects.filter(action="event.submission_stage.extension_granted").exists()
    assert refused(lambda: stage_staff.extend(actor=w.manager, event_id=w.event.pk, stage_id=one.pk, values={
        "operation_id": uuid4(), "team_id": team.pk, "until": w.event.ends_at + timedelta(minutes=1),
        "reason": "Too late"}))[0] == "invalid_extension"
    with pytest.raises(RuntimeError):
        StageExtension.objects.filter(pk=granted["id"]).update(reason="edited")
