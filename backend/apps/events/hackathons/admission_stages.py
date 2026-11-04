"""Review stages and their panels (#128 C-33): one writer, inside the admission command boundary.

Stage settings are configuration (full event manager authority). Panels and assignments
are review operations (`review_applications`). A stage's criteria, blind switch and review
target freeze at its first review; its name, guidance, window and state stay editable.
"""
import re

from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .admission_errors import check_version, fail
from .admission_stage_models import MAX_CRITERIA, MAX_STAGES, AdmissionStage, AdmissionStageEntry, AdmissionStageReviewer
from .admission_transactions import command

STAGES = "events.application_stages"
FROZEN = ("criteria", "blind", "reviews_per_application")
EDITABLE = ("name", "guidance", "opens_at", "closes_at", "assignment_strategy", *FROZEN)
MOVES = {"draft": {"open"}, "open": {"closed"}, "closed": {"open"}}
KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def require_feature(event):
    if not feature_enabled(event.makerspace, STAGES):
        fail("not_found", "Not found.", status=404)


def stages_for(event_id):
    return AdmissionStage.objects.filter(event_id=event_id).order_by("position")


def current_stage(application):
    """The stage an application stands in: its newest entry, else the event's first stage."""
    entry = AdmissionStageEntry.objects.filter(application=application).order_by("-pk").select_related("stage").first()
    if entry is not None:
        return None if entry.kind == AdmissionStageEntry.Kind.LEFT else entry.stage
    return stages_for(application.event_id).first()


def next_stage(stage):
    return stages_for(stage.event_id).filter(position__gt=stage.position).first()


def enter_locked(ctx, application, stage, *, kind="entered", decision=None, reason_code=""):
    return AdmissionStageEntry.objects.create(event=ctx.event, application=application, stage=stage, kind=kind,
                                              decision=decision, reason_code=reason_code, actor=ctx.actor)


def materialize_entry_locked(ctx, application, stage):
    """Record the implicit first-stage entry the first time the stage acts on an application."""
    if not AdmissionStageEntry.objects.filter(application=application).exists():
        enter_locked(ctx, application, stage, reason_code="first_stage")


def validate_criteria(criteria):
    if not isinstance(criteria, list) or len(criteria) > MAX_CRITERIA:
        fail("invalid_criteria", f"Use at most {MAX_CRITERIA} criteria.", status=400)
    keys = set()
    for row in criteria:
        if (not isinstance(row, dict) or set(row) - {"key", "label", "guidance"} or not KEY.match(str(row.get("key", "")))
                or not str(row.get("label", "")).strip() or len(str(row["label"])) > 120
                or len(str(row.get("guidance", ""))) > 500 or row["key"] in keys):
            fail("invalid_criteria", "Each criterion needs a unique key and a label; scores run from 1 to 5.", status=400)
        keys.add(row["key"])
    return criteria


def _validate(stage):
    validate_criteria(stage.criteria)
    if not 1 <= stage.reviews_per_application <= 20:
        fail("invalid_review_target", "A stage needs 1 to 20 reviews per application.", status=400)
    if stage.opens_at and stage.closes_at and stage.closes_at <= stage.opens_at:
        fail("invalid_window", "The close time must follow the opening time.", status=400)
    if not stage.name.strip():
        fail("invalid_name", "Name the stage.", status=400)


def create(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="stage.create", permission=None) as ctx:
        require_feature(ctx.event)
        if ctx.reference:
            return get_object_or_404(AdmissionStage, pk=ctx.reference["id"], event=ctx.event)
        position = (stages_for(event_id).aggregate(value=Max("position"))["value"] or 0) + 1
        if position > MAX_STAGES:
            fail("too_many_stages", f"An event can have at most {MAX_STAGES} review stages.", status=400)
        stage = AdmissionStage(event=ctx.event, position=position, created_by=actor,
                               **{key: data[key] for key in EDITABLE if key in data})
        _validate(stage)
        stage.save()
        audit.record(actor, "event.admission_stage.created", makerspace=ctx.event.makerspace, target=stage,
                     meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "position": stage.position,
                           "reviews_per_application": stage.reviews_per_application, "blind": stage.blind})
        ctx.finish("admission_stage", stage.pk, status=201)
        return stage


def update(*, event_id, stage_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"stage.update:{stage_id}", permission=None) as ctx:
        require_feature(ctx.event)
        stage = get_object_or_404(AdmissionStage.objects.select_for_update(), pk=stage_id, event=ctx.event)
        if ctx.reference:
            return stage
        check_version(stage, data["expected_version"])
        changed = [key for key in EDITABLE if key in data and data[key] != getattr(stage, key)]
        if stage.frozen_at and set(changed) & set(FROZEN):
            fail("stage_frozen", "Criteria, blind review and the review target are fixed once a stage has reviews.")
        for key in changed:
            setattr(stage, key, data[key])
        target = data.get("state")
        if target and target != stage.state:
            if target not in MOVES[stage.state]:
                fail("invalid_transition", "This stage cannot move to that state.")
            stage.state = target
            changed.append("state")
        _validate(stage)
        stage.version += 1
        stage.save()
        audit.record(actor, "event.admission_stage.updated", makerspace=ctx.event.makerspace, target=stage,
                     meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "position": stage.position,
                           "changed": sorted(changed), "state": stage.state})
        ctx.finish("admission_stage", stage.pk)
        return stage


def set_panel(*, event_id, stage_id, actor, data):
    from apps.accounts.models import User
    from apps.accounts.staff_identity import person_q
    reviewer_ids = sorted(set(data["reviewer_ids"]))
    with command(event_id=event_id, actor=actor, data=data, action=f"stage.panel:{stage_id}",
                 permission="review_applications", account_ids=tuple(reviewer_ids)) as ctx:
        require_feature(ctx.event)
        stage = get_object_or_404(AdmissionStage.objects.select_for_update(), pk=stage_id, event=ctx.event)
        if ctx.reference:
            return stage
        check_version(stage, data["expected_version"])
        people = set(User.objects.filter(person_q(), pk__in=reviewer_ids, is_active=True, access_status="active")
                     .values_list("pk", flat=True))
        if people != set(reviewer_ids):
            fail("not_found", "Not found.", status=404)
        live = {row.reviewer_id: row for row in AdmissionStageReviewer.objects.select_for_update()
                .filter(stage=stage, removed_at__isnull=True)}
        added = [pk for pk in reviewer_ids if pk not in live]
        removed = [row for pk, row in live.items() if pk not in people]
        for pk in added:
            AdmissionStageReviewer.objects.create(stage=stage, reviewer_id=pk, added_by=actor)
        now = timezone.now()
        for row in removed:
            row.removed_at = now
            row.save(update_fields=["removed_at"])
        stage.version += 1
        stage.save(update_fields=["version"])
        audit.record(actor, "event.admission_stage.panel_changed", makerspace=ctx.event.makerspace, target=stage,
                     meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "position": stage.position,
                           "added": len(added), "removed": len(removed)})
        ctx.finish("admission_stage", stage.pk)
        return stage
