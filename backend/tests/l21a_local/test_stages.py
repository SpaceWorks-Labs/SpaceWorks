"""L21a multi-stage review: stage rules, panel isolation, seeded assignment, advance and stale skips."""
from types import SimpleNamespace

import pytest

from apps.events import event_authority
from apps.events.hackathons import admission_stage_assign as assign
from apps.events.hackathons import admission_stage_flow, admission_stage_review, admission_stages
from apps.events.hackathons.admission_decisions import finish_batch, stage as stage_decisions
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_stage_models import AdmissionStage, AdmissionStageAssignment, AdmissionStageEntry
from apps.events.judging.assignment_planner import plan_assignments
from apps.audit.models import AuditLog
from tests.events.programme.admission.test_support import cmd, submitted, world  # noqa: F401
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db
CRITERIA = [{"key": "fit", "label": "Fit"}, {"key": "skill", "label": "Skill"}]


@pytest.fixture
def staged(world, monkeypatch):  # noqa: F811
    for module in (admission_stages, admission_stage_flow):
        monkeypatch.setattr(module, "feature_enabled", lambda *args: True)
    monkeypatch.setattr("apps.events.hackathons.admission_stage_review.require_feature", lambda event: None)
    world.config.review_mode = "batch"
    world.config.save()
    return world


def make_stage(world, **values):
    data = cmd(0, name=values.pop("name", "Screen"), criteria=values.pop("criteria", CRITERIA), **values)
    return admission_stages.create(event_id=world.event.pk, actor=world.owner, data=data)


def open_stage(world, stage):
    return admission_stages.update(event_id=world.event.pk, stage_id=stage.pk, actor=world.owner,
                                   data=cmd(stage.version, state="open"))


def panel(world, stage, *people):
    stage.refresh_from_db()
    return admission_stages.set_panel(event_id=world.event.pk, stage_id=stage.pk, actor=world.owner,
                                      data=cmd(stage.version, reviewer_ids=[p.pk for p in people]))


@pytest.mark.parametrize("target, ok", [(0, False), (1, True), (20, True), (21, False)])
def test_stage_review_target_runs_from_1_to_20(staged, target, ok):
    stage = AdmissionStage(event=staged.event, position=1, name="S", reviews_per_application=target)
    if ok:
        admission_stages._validate(stage)
    else:
        with pytest.raises(ProgrammeError):
            admission_stages._validate(stage)


def test_judging_rounds_keep_their_floor_of_three():
    with pytest.raises(ValueError):
        plan_assignments([1, 2], [10, 11, 12], target_views=2)
    assert plan_assignments([1, 2], [10, 11], target_views=1, minimum_views=1).pairs


def test_at_most_twenty_stages_and_ten_criteria(staged):
    for index in range(20):
        make_stage(staged, name=f"S{index}")
    with pytest.raises(ProgrammeError) as exc:
        make_stage(staged, name="One too many")
    assert exc.value.detail["code"] == "too_many_stages"
    with pytest.raises(ProgrammeError):
        admission_stages.validate_criteria([{"key": f"k{i}", "label": "L"} for i in range(11)])


def test_seed_reproducibility_and_fingerprint_checked_apply(staged):
    first, second = submitted(staged, state="submitted"), submitted(staged, staged.other, state="submitted")
    reviewers = [account(f"rev-{i}") for i in range(4)]
    stage = make_stage(staged, reviews_per_application=2, assignment_strategy="random")
    panel(staged, stage, *reviewers)
    stage.refresh_from_db()
    one = assign.preview(event=staged.event, stage=stage, seed="abc", strategy="random")
    again = assign.preview(event=staged.event, stage=stage, seed="abc", strategy="random")
    assert one["fingerprint"] == again["fingerprint"] and one["pairs"] == again["pairs"]
    assert len(one["pairs"]) == 4 and not one["deficits"]
    balanced = assign.preview(event=staged.event, stage=stage, seed="abc", strategy="balanced")
    assert balanced["fingerprint"] == assign.preview(event=staged.event, stage=stage, seed="abc",
                                                     strategy="balanced")["fingerprint"]
    with pytest.raises(ProgrammeError) as exc:
        assign.apply(event_id=staged.event.pk, stage_id=stage.pk, actor=staged.owner,
                     data=cmd(0, seed="abc", strategy="random", fingerprint="0" * 64))
    assert exc.value.detail["code"] == "plan_changed"
    applied, created = assign.apply(event_id=staged.event.pk, stage_id=stage.pk, actor=staged.owner,
                                    data=cmd(0, seed="abc", strategy="random", fingerprint=one["fingerprint"]))
    assert created == 4 and applied.assignment_seed == "abc" and applied.assignment_fingerprint == one["fingerprint"]
    assert AdmissionStageEntry.objects.filter(application__in=[first, second], kind="entered").count() == 2
    assert AuditLog.objects.filter(action="event.admission_stage.assigned").exists()


def test_panel_reviewer_sees_only_own_assignments_and_holds_no_event_authority(staged):
    app = submitted(staged, state="submitted")
    reviewer, outsider = account("panel-a"), account("not-on-panel")
    stage = make_stage(staged, reviews_per_application=1)
    panel(staged, stage, reviewer)
    stage = open_stage(staged, AdmissionStage.objects.get(pk=stage.pk))
    plan = assign.preview(event=staged.event, stage=stage, seed="s1")
    assign.apply(event_id=staged.event.pk, stage_id=stage.pk, actor=staged.owner,
                 data=cmd(0, seed="s1", strategy=plan["strategy"], fingerprint=plan["fingerprint"]))
    stage.refresh_from_db()
    rows = admission_stage_review.assignments_for(reviewer, stage)
    assert [row["application"]["id"] for row in rows] == [app.pk]
    with pytest.raises(ProgrammeError) as exc:
        admission_stage_review.assignments_for(outsider, stage)
    assert exc.value.status_code == 404
    # The panel seat is no event authority: no permission at all on the event itself.
    import apps.events.event_authority as real  # the world fixture patched require/get_event only
    assert not real.can(reviewer, staged.event, "review_applications")
    assert not real.can(reviewer, staged.event, None)
    assert event_authority is real


def test_criteria_freeze_at_first_review_and_advance_moves_to_next_stage(staged):
    app = submitted(staged, state="submitted")
    reviewer = account("panel-b")
    first = make_stage(staged, reviews_per_application=1)
    second = make_stage(staged, name="Interview")
    panel(staged, first, reviewer)
    first = open_stage(staged, AdmissionStage.objects.get(pk=first.pk))
    plan = assign.preview(event=staged.event, stage=first, seed="s2")
    assign.apply(event_id=staged.event.pk, stage_id=first.pk, actor=staged.owner,
                 data=cmd(0, seed="s2", strategy=plan["strategy"], fingerprint=plan["fingerprint"]))
    row = AdmissionStageAssignment.objects.get(stage=first, reviewer=reviewer)
    admission_stage_review.submit(actor=reviewer, stage_id=first.pk, assignment_id=row.pk,
                                  data={"scores": {"fit": 4, "skill": 5}, "notes": ""})
    first.refresh_from_db()
    assert first.frozen_at is not None
    with pytest.raises(ProgrammeError) as exc:
        admission_stages.update(event_id=staged.event.pk, stage_id=first.pk, actor=staged.owner,
                                data=cmd(first.version, blind=True))
    assert exc.value.detail["code"] == "stage_frozen"
    app.refresh_from_db()
    batch = stage_decisions(event_id=staged.event.pk, actor=staged.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "advance",
        "reason_code": "review_complete", "stage_id": first.pk}]))
    finish_batch(event_id=staged.event.pk, actor=staged.owner, data=cmd(batch.version, batch_id=batch.pk))
    app.refresh_from_db()
    assert app.state == "submitted" and admission_stages.current_stage(app).pk == second.pk
    assert list(AdmissionStageEntry.objects.filter(application=app).values_list("kind", "stage_id")) == [
        ("entered", first.pk), ("advanced", first.pk), ("entered", second.pk)]
    with pytest.raises(ValueError):
        AdmissionStageEntry.objects.filter(application=app).first().save()


def test_advance_needs_stage_coverage_and_stale_decisions_are_skipped_on_release(staged):
    app = submitted(staged, state="submitted")
    first = make_stage(staged, reviews_per_application=1)
    make_stage(staged, name="Final")
    batch = stage_decisions(event_id=staged.event.pk, actor=staged.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "advance",
        "reason_code": "review_complete", "stage_id": first.pk}]))
    with pytest.raises(ProgrammeError) as exc:
        finish_batch(event_id=staged.event.pk, actor=staged.owner, data=cmd(batch.version, batch_id=batch.pk))
    assert exc.value.detail["code"] == "review_coverage_required"
    finish_batch(event_id=staged.event.pk, actor=staged.owner, data=cmd(batch.version, batch_id=batch.pk), cancel=True)
    stale = stage_decisions(event_id=staged.event.pk, actor=staged.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "reject",
        "reason_code": "review_complete", "review_override_code": "chair_override"}]))
    app.version += 1  # the application changed after the decision was staged
    app.save(update_fields=["version"])
    finish_batch(event_id=staged.event.pk, actor=staged.owner, data=cmd(stale.version, batch_id=stale.pk))
    app.refresh_from_db()
    assert app.state == "submitted"
    assert AuditLog.objects.filter(action="event.application.decision_skipped").exists()


def test_stage_routes_are_off_when_the_capability_is_off(world):  # noqa: F811
    with pytest.raises(ProgrammeError) as exc:
        make_stage(world)
    assert exc.value.status_code == 404
    assert admission_stage_flow.stage_for_staging(world.event, SimpleNamespace(), {"outcome": "offer"}) is None
