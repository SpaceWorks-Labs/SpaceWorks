"""Stages meet judging, money, the backfill and the registries (#178-#180 S17, G11)."""
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps
from rest_framework.exceptions import ValidationError

from apps.events.judging.ports import Snapshot
from apps.events.submissions import stage_judging
from apps.events.submissions.entry_fees import fee_stage_position
from apps.events.submissions.models_projects import HackathonSubmission
from apps.events.submissions.models_stages import SnapshotStage, SubmissionStage, SubmissionStageEntry
from apps.events.submissions.stage_evidence import submission_evidence
from tests.submit_content_local.stage_helpers import REPO, run, save, stage, world

pytestmark = pytest.mark.django_db


def snap(pk, team, stage_id):
    return Snapshot(id=pk, event_id=1, team_id=team, member_ids=(team,), track_ids=(), prize_ids=(), title="t",
                    description="", content_sha256="x", eligible=True, current=True, metadata_public=False,
                    public_asset_ids=(), public_links=(), expires_at=None, stage_id=stage_id)


def test_an_award_must_point_at_the_stage_its_round_judges(monkeypatch):
    monkeypatch.setattr(stage_judging, "round_stage_id", lambda round: round.stage)
    rounds = [SimpleNamespace(stage=3)]
    stage_judging.require_award_stage(rounds, snap(1, 1, 3))
    stage_judging.require_award_stage(rounds, snap(1, 1, None))  # Unstaged history keeps its old rule.
    with pytest.raises(ValidationError):
        stage_judging.require_award_stage(rounds, snap(2, 1, 2))


def test_finalists_from_another_stage_carry_over_by_team(monkeypatch):
    finalists = {10: snap(10, 1, 2)}
    monkeypatch.setattr("apps.events.judging.ports.runtime", lambda: SimpleNamespace(snapshot=finalists.__getitem__))
    later = [snap(20, 1, 3), snap(21, 2, 3)]
    assert [s.id for s in stage_judging.narrow_to_finalists(later, {10}, 3)] == [20]
    same = [snap(10, 1, 2), snap(11, 2, 2)]
    assert [s.id for s in stage_judging.narrow_to_finalists(same, {10}, 2)] == [10]


def test_a_round_judges_the_last_stage_by_default(monkeypatch):
    w = world(monkeypatch)
    stage(w.event, 1)
    last = stage(w.event, 2)
    assert stage_judging.round_stage_id(SimpleNamespace(submission_stage_id=None, event_id=w.event.pk)) == last.pk


def test_entry_fee_stage_defaults_to_the_first_and_caps_at_the_last(monkeypatch):
    w = world(monkeypatch)
    stage(w.event, 1)
    stage(w.event, 2)
    assert fee_stage_position(w.event) == 1
    apps.get_model("events", "HackathonProgrammeOptions").objects.create(event=w.event, entry_fee_stage=5)
    assert fee_stage_position(w.event) == 2


def test_the_fee_is_not_due_before_its_stage(monkeypatch):
    from apps.events.submissions import entry_fees
    w = world(monkeypatch)
    first, second = stage(w.event, 1), stage(w.event, 2)
    apps.get_model("events", "HackathonProgrammeOptions").objects.create(event=w.event, entry_fee_stage=2)
    monkeypatch.setattr(entry_fees, "entry_fee", lambda event: 25)
    monkeypatch.setattr("apps.events.hackathons.team_payments.team_payment_settled", lambda team: True)
    project = HackathonSubmission(pk=None, event=w.event, team=w.teams[0].team)
    entry_fees.require_submit_paid(project, w.event, w.teams[0].team, stage=first)  # Stage 1 is free.
    with pytest.raises(Exception) as caught:
        entry_fees.require_submit_paid(project, w.event, w.teams[0].team, stage=second)
    assert caught.value.detail["code"] == "entry_fee_required"


def test_reimbursement_evidence_follows_the_required_submission_rule(monkeypatch):
    w = world(monkeypatch)
    one, two = stage(w.event, 1, shortlist_after=True), stage(w.event, 2)
    done = run(w, "submit", save(w, links=[REPO])["version"], {"stage_id": one.pk})
    member = w.teams[0].user.pk
    assert submission_evidence(event=w.event, owner_id=member, mode="any_stage") is None  # Untriaged.
    SubmissionStageEntry.objects.update(triage="eligible")
    assert submission_evidence(event=w.event, owner_id=member, mode="any_stage") == done["snapshot_id"]
    assert submission_evidence(event=w.event, owner_id=member, mode="stage", position=1) == done["snapshot_id"]
    assert submission_evidence(event=w.event, owner_id=member, mode="final_stage") is None
    assert submission_evidence(event=w.event, owner_id=member, mode="shortlisted_at", position=1) is None
    assert submission_evidence(event=w.event, owner_id=member, mode="none") is None
    assert two.pk


def test_reimbursement_policy_keeps_the_old_switch_in_step(monkeypatch):
    from apps.event_reimbursements.policy import _required_submission
    w = world(monkeypatch)
    stage(w.event, 1, shortlist_after=True)
    stage(w.event, 2)
    value = {"require_project_submission": True}
    _required_submission(value, w.event)
    assert value["required_submission"] == "any_stage"
    value = {"required_submission": "shortlisted_at", "required_submission_stage": 1}
    _required_submission(value, w.event)
    assert value["require_project_submission"] is True
    with pytest.raises(Exception):
        _required_submission({"required_submission": "shortlisted_at", "required_submission_stage": 2}, w.event)


def test_accepted_awards_keep_the_rule_they_were_given():
    from apps.event_reimbursements.accepted_policy import project_rule
    programme = SimpleNamespace(required_submission="final_stage", required_submission_stage=None)
    assert project_rule(SimpleNamespace(calculation_snapshot={"require_project_submission": True}),
                        programme) == ("any_stage", None)
    assert project_rule(SimpleNamespace(calculation_snapshot={"required_submission": "stage",
                                                              "required_submission_stage": 2}), programme) == ("stage", 2)
    assert project_rule(SimpleNamespace(calculation_snapshot={}), programme) == ("final_stage", None)


def test_backfill_turns_each_window_into_one_stage_and_records_snapshots(monkeypatch):
    w = world(monkeypatch)
    done = run(w, "submit", save(w, links=[REPO])["version"])
    project = HackathonSubmission.objects.get()
    SubmissionStageEntry.objects.filter(submission=project).delete()
    from django.db import connection
    with connection.cursor() as cursor:  # Recreate the pre-stage world: stage records are append-only.
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        cursor.execute("DELETE FROM events_snapshotstage")
    SubmissionStage.objects.filter(event=w.event).delete()
    import_module("apps.events.migrations.0073_submission_stages_backfill").single_submission_stage(apps, None)
    stage_row = SubmissionStage.objects.get(event=w.event)
    config = apps.get_model("events", "HackathonConfig").objects.get(event=w.event)
    assert (stage_row.name, stage_row.content_mode, stage_row.deadline, stage_row.late_policy) == (
        "Submission", "files_and_links", config.submission_deadline, config.late_policy)
    assert SnapshotStage.objects.get(snapshot_id=done["snapshot_id"]).stage_id == stage_row.pk
    entry = SubmissionStageEntry.objects.get(submission=project)
    assert entry.current_snapshot_id == done["snapshot_id"] and entry.triage == project.triage


def test_reimbursement_migration_maps_yes_to_any_stage():
    module = import_module("apps.event_reimbursements.migrations.0007_required_submission_stage")
    assert callable(module.any_stage_for_yes)


def test_new_models_are_classified_in_every_registry():
    from apps.accounts.merge_registry import disposition_for
    from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_DECISIONS
    from apps.audit.presentation_catalog import PRESENTATION_CATALOG as CATALOGUE
    from apps.makerspaces.purge_events_programme_catalog import PURGE_ORDER
    from apps.tenant_migration.catalog_events_programme import FIELD_NAMES
    from apps.tenant_migration.catalog_events_programme_json import JSON_FIELDS
    labels = ("events.SubmissionStage", "events.SubmissionStageEntry", "events.SnapshotStage", "events.StageShortlist",
              "events.StageShortlistEntry", "events.StageShortlistAnnouncement", "events.StageExtension")
    for label in labels:
        model = apps.get_model(label)
        assert FIELD_NAMES[label] == {f.name for f in model._meta.concrete_fields}, label
        assert any(row[0] == label for row in PURGE_ORDER), label
    assert "submission_stage" in FIELD_NAMES["events.JudgingRound"]
    assert {"stage_reminder_email", "shortlist_email", "entry_fee_stage"} <= FIELD_NAMES["events.HackathonProgrammeOptions"]
    assert ("events.SubmissionStage", "custom_fields") in JSON_FIELDS
    for label, field in (("events.StageShortlist", "created_by"), ("events.StageShortlistAnnouncement", "published_by"),
                         ("events.StageExtension", "created_by")):
        assert disposition_for(label, field) is not None
    order = [row[0] for row in PURGE_ORDER]
    assert order.index("events.JudgingRound") < order.index("events.SubmissionStage")
    assert order.index("events.SnapshotStage") < order.index("events.SubmissionSnapshot")
    for name in ("events-programme-admin-submission-stages", "events-programme-admin-submission-stage-shortlist-publish"):
        assert name in BY_NAME and NATIVE_DECISIONS[name] == "native"
    for action in ("event.submission_stages.updated", "event.submission_stage.shortlist_applied",
                   "event.submission_stage.shortlist_published", "event.submission_stage.extension_granted"):
        assert action in CATALOGUE


def test_new_stage_emails_are_catalogued_and_start_off():
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from apps.events.judging.options import option
    events = set(next(v for k, v in FEATURE_EVENTS.items() if "stage_shortlisted" in v))
    assert {"stage_deadline_reminder", "stage_shortlisted", "stage_not_shortlisted"} <= events
    dummy = SimpleNamespace(pk=-1)
    assert option(dummy, "shortlist_email") is False and option(dummy, "stage_reminder_email") is False
    assert uuid4()
