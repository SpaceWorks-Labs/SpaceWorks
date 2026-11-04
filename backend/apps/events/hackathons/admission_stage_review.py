"""The panel reviewer's workspace: only their own assignments in stages whose panel they sit on.

Panel membership is the whole authority here and it widens nothing: a reviewer-only
person reads no event, roster, decision or configuration, only the application answers
the form discloses to reviewers (identity stripped when the stage is blind).
"""
import json

from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.staff_identity import is_person
from apps.audit import services as audit
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable

from .admission_errors import fail
from .admission_models import HackathonConfig
from .admission_stage_models import AdmissionStage, AdmissionStageAssignment, AdmissionStageReview, AdmissionStageReviewer
from .admission_stages import require_feature
from .review_projection import alias, reviewer_answers


def _active(actor):
    from apps.events.event_authority import _active
    return _active(actor) and is_person(actor)


def on_panel(actor, stage):
    return AdmissionStageReviewer.objects.filter(stage=stage, reviewer=actor, removed_at__isnull=True).exists()


def require_panel(actor, stage, *, open_only=True):
    event = stage.event
    if (not _active(actor) or not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events")
            or not on_panel(actor, stage)):
        fail("not_found", "Not found.", status=404)
    require_feature(event)
    if open_only and stage.state != AdmissionStage.State.OPEN:
        fail("stage_not_open", "This review stage is not open.")
    now = timezone.now()
    if open_only and ((stage.opens_at and now < stage.opens_at) or (stage.closes_at and now >= stage.closes_at)):
        fail("stage_not_open", "This review stage is outside its review window.")
    return stage


def my_stages(actor):
    if not _active(actor):
        return []
    rows = (AdmissionStage.objects.filter(panel__reviewer=actor, panel__removed_at__isnull=True,
                                          state=AdmissionStage.State.OPEN, event__status="published")
            .select_related("event__makerspace").order_by("event__starts_at", "position").distinct())
    result = []
    for stage in rows:
        try:
            require_panel(actor, stage)
        except Exception:
            continue
        mine = AdmissionStageAssignment.objects.filter(stage=stage, reviewer=actor)
        result.append({**project_stage(stage), "event_title": stage.event.title,
                       "assigned": mine.filter(state="assigned").count(),
                       "submitted": mine.filter(state="submitted").count()})
    return result


def project_stage(stage):
    return {"id": stage.pk, "event_id": stage.event_id, "position": stage.position, "name": stage.name,
            "state": stage.state, "blind": stage.blind, "criteria": stage.criteria, "guidance": stage.guidance,
            "reviews_per_application": stage.reviews_per_application, "opens_at": stage.opens_at,
            "closes_at": stage.closes_at}


def project_assignment(assignment):
    stage, application = assignment.stage, assignment.application
    config = HackathonConfig.objects.get(event_id=stage.event_id)
    answers = reviewer_answers(json.loads(application.answers_snapshot), config.application_form, blind=stage.blind)
    review = getattr(assignment, "review", None) if assignment.state == "submitted" else None
    return {"id": assignment.pk, "stage_id": stage.pk, "state": assignment.state,
            "application": {"id": application.pk, "alias": alias(application.event_id, application.pk),
                            "answers": answers if assignment.state != "recused" else []},
            "scores": review.scores if review else None,
            "allowed_actions": ["submit", "recuse"] if assignment.state == "assigned" else []}


def assignments_for(actor, stage):
    require_panel(actor, stage, open_only=False)
    rows = AdmissionStageAssignment.objects.filter(stage=stage, reviewer=actor).select_related(
        "stage", "application").order_by("assigned_at", "pk")
    return [project_assignment(row) for row in rows]


def submit(*, actor, stage_id, assignment_id, data):
    from apps.events.services_write_boundary import write_boundary
    initial = get_object_or_404(AdmissionStage.objects.select_related("event__makerspace"), pk=stage_id)
    with write_boundary(initial.event, actor=actor):
        stage = AdmissionStage.objects.select_for_update().select_related("event__makerspace").get(pk=stage_id)
        require_panel(actor, stage)
        row = get_object_or_404(AdmissionStageAssignment.objects.select_for_update(), pk=assignment_id,
                                stage=stage, reviewer=actor)
        if row.state != AdmissionStageAssignment.State.ASSIGNED:
            fail("invalid_transition", "This review is already finished.")
        from .review_workflow import conflicted
        if "recusal_code" in data:
            row.state = AdmissionStageAssignment.State.RECUSED
        else:
            if conflicted(stage.event_id, actor.pk, row.application):
                fail("review_conflict", "Recuse from this application.", status=403)
            keys = {criterion["key"] for criterion in stage.criteria}
            scores = data.get("scores") or {}
            if set(scores) != keys or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
                fail("invalid_scores", "Score every criterion from 1 to 5.", status=400)
            AdmissionStageReview.objects.create(assignment=row, scores=scores, notes=data.get("notes", ""))
            row.state, row.submitted_at = AdmissionStageAssignment.State.SUBMITTED, timezone.now()
            if stage.frozen_at is None:
                stage.frozen_at = row.submitted_at
                stage.save(update_fields=["frozen_at"])
        row.save()
        if row.state == AdmissionStageAssignment.State.RECUSED:
            audit.record(actor, "event.admission_stage.review_recused", makerspace=stage.event.makerspace,
                         target=row, meta={"event_id": stage.event_id, "stage_id": stage.pk, "assignment_id": row.pk})
        else:
            audit.record(actor, "event.admission_stage.review_submitted", makerspace=stage.event.makerspace,
                         target=row, meta={"event_id": stage.event_id, "stage_id": stage.pk, "assignment_id": row.pk})
        return row


def coverage(stage, application):
    """Distinct live panel reviewers who submitted for this application in this stage."""
    from .review_workflow import conflicted
    rows = AdmissionStageAssignment.objects.filter(stage=stage, application=application, state="submitted",
                                                   review__isnull=False)
    panel = set(AdmissionStageReviewer.objects.filter(stage=stage, removed_at__isnull=True)
                .values_list("reviewer_id", flat=True))
    return len({row.reviewer_id for row in rows if row.reviewer_id in panel
                and not conflicted(stage.event_id, row.reviewer_id, application)})
