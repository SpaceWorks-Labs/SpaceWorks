"""Single writer for stage definitions, publication and assignment activation."""
from django.utils import timezone
from apps.events import event_authority
from .form_provider import append_locked
from apps.payments.event_payouts.errors import require
from .transactions import command
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .policy import require_stage_schema, validate_audience, validate_blocking
from .trigger_service import applicable, schedule


CONFIG_FIELDS = frozenset({"slug", "title", "stage", "activation_point", "opening_mode", "opens_at",
    "opening_offset_seconds", "due_mode", "due_at", "due_after_seconds", "due_event_offset_seconds",
    "reminder_offsets", "required", "missed_action", "blocked_actions", "lock_on_next_stage", "audience"})


def validate_definition(row, event, actor):
    from apps.events.hackathons.admission_models import HackathonConfig
    from .deadlines import reminder_times, resolve
    from apps.events.contributions.models_roles import ROLES
    from apps.events.judging.models_definitions import HackathonTrack
    validate_audience(row.audience)
    require(set(row.audience["roles"]) <= {"participant", *(value for value, _ in ROLES)},
            "invalid_stage_audience", status=400)
    tracks = row.audience["track_ids"]
    require(HackathonTrack.objects.filter(event=event, pk__in=tracks).count() == len(tracks),
            "invalid_stage_audience", status=400)
    validate_blocking(stage=row.stage, activation_point=row.activation_point, required=row.required,
        missed_action=row.missed_action, blocked_actions=row.blocked_actions,
        hackathon=HackathonConfig.objects.filter(event=event, enabled=True).exists())
    if row.missed_action == "block":
        require(event_authority.can_manage_grants(actor, event), "full_manager_required", status=403)
    # Model nullability describes the mode union; a valid union deliberately has
    # empty inactive columns. Validate populated scalars plus the union policy,
    # rather than treating every null/empty JSON column as a required form field.
    for name in CONFIG_FIELDS:
        model_field, value = row._meta.get_field(name), getattr(row, name)
        if model_field.get_internal_type() == "JSONField" or value is None and model_field.null:
            continue
        if name == "activation_point" and value == "":
            continue
        model_field.clean(value, row)
    row.validate_constraints()
    triggered_at = event.starts_at if row.stage == "pre_event" else event.ends_at if row.stage == "post_event" else timezone.now()
    resolved = resolve(triggered_at=triggered_at, event_start=event.starts_at, event_end=event.ends_at,
        **{key: getattr(row, key) for key in ("opening_mode", "due_mode", "opens_at", "opening_offset_seconds",
            "due_at", "due_after_seconds", "due_event_offset_seconds")})
    reminder_times(triggered_at=triggered_at, due_at=resolved.due_at, offsets=row.reminder_offsets)


def configure(*, event_id, actor, data, stage_form_id=None):
    with command(event_id=event_id, actor=actor, data=data, action=f"stage.configure:{stage_form_id or 'new'}",
                 permission="edit_details", reimbursement=False) as ctx:
        if ctx.replay:
            return ctx.replay
        row = (EventStageForm.objects.select_for_update().get(pk=stage_form_id, event=ctx.event)
               if stage_form_id else EventStageForm(event=ctx.event, created_by=ctx.actor))
        require(data["expected_version"] == (row.version if stage_form_id else 0), "stale_version")
        settings = data["settings"]
        require(not set(settings) - CONFIG_FIELDS, "invalid_stage_settings", status=400)
        for key, value in settings.items():
            setattr(row, key, value)
        validate_definition(row, ctx.event, ctx.actor)
        require(row.state != "retired", "stage_retired")
        if stage_form_id:
            row.version += 1
        row.save()
        if "schema" in data:
            require_stage_schema(data["schema"])
            row.current_revision = append_locked(event=ctx.event, actor=ctx.actor,
                target=row, schema=data["schema"])
            row.save(update_fields=["current_revision"])
        ctx.audit("event.stage_form.configured", row, stage_form_id=row.pk)
        ctx.event.version += 1
        ctx.event.save(update_fields=["version"])
        return ctx.finish(row, form_id=str(row.form_id), revision_id=row.current_revision_id)


def transition(*, event_id, actor, data, stage_form_id, publish):
    with command(event_id=event_id, actor=actor, data=data, action=f"stage.{'publish' if publish else 'retire'}:{stage_form_id}",
                 permission="edit_details", reimbursement=False) as ctx:
        if ctx.replay:
            return ctx.replay
        row = EventStageForm.objects.select_for_update().get(pk=stage_form_id, event=ctx.event)
        ctx.cas(row)
        validate_definition(row, ctx.event, ctx.actor)
        require(row.current_revision_id is not None, "stage_form_revision_required")
        require_stage_schema(row.current_revision.schema)
        require(row.state != "retired" if publish else row.state == "published", "invalid_stage_transition")
        row.state, row.version = ("published" if publish else "retired"), row.version + 1
        if publish:
            row.published_at = timezone.now()
        else:
            row.retired_at = timezone.now()
        row.save()
        ctx.audit("event.stage_form.published" if publish else "event.stage_form.retired", row,
                  stage_form_id=row.pk, revision_id=row.current_revision_id)
        ctx.event.version += 1
        ctx.event.save(update_fields=["version"])
        return ctx.finish(row)


def activate_locked(*, definition, subject, locks, due_at=None):
    from .transactions import require_outer
    from .trigger_service import trigger_at
    require_outer(locks, subject.event)
    require(subject.owner_member_id in locks.account_ids, "owner_fence_required")
    require(definition.state == "published", "stage_not_published")
    require_stage_schema(definition.current_revision.schema)
    existing = StageFormAssignment.objects.filter(stage_form=definition, owner_member_id=subject.owner_member_id).first()
    if existing:
        return existing
    candidate = applicable(definition, subject)
    if due_at is None and candidate is None:
        return None
    triggered = trigger_at(definition, subject)
    require(triggered is not None, "stage_not_applicable")
    resolved = candidate[1] if candidate else schedule(definition, subject=subject, triggered_at=triggered)
    opening = timezone.now() if due_at else resolved.opens_at
    due = due_at or resolved.due_at
    require(due > opening and (due_at is None or due > timezone.now()), "stage_deadline_requires_review")
    row = StageFormAssignment.objects.create(stage_form=definition, event=subject.event,
        owner_member_id=subject.owner_member_id, registration=subject.registration, application=subject.application,
        creation_operation_id=subject.creation_operation_id, trigger_key=definition.stage,
        trigger_revision=getattr(subject.application or subject.registration, "version", 1),
        pinned_form_revision=definition.current_revision, triggered_at=triggered,
        opens_at=opening, base_due_at=due, effective_due_at=due,
        state="open" if timezone.now() < due else "overdue")
    StageFormResponse.objects.create(assignment=row, event=subject.event, owner_member_id=subject.owner_member_id,
        form_revision=definition.current_revision, answer_event_date_revision=subject.event.event_date_revision)
    from .notices import enqueue_locked
    enqueue_locked(row, "opened" if row.state == "open" else "overdue")
    return row


def reconcile_deadlines_locked(*, event, now, locks):
    from .response_workflow import lock_at_deadline_locked
    from .transactions import require_outer
    require_outer(locks, event)
    for row in StageFormAssignment.objects.select_for_update().filter(event=event,
        owner_member_id__in=locks.account_ids).exclude(state="cancelled").order_by("pk"):
        response = StageFormResponse.objects.select_for_update().get(assignment=row)
        if now >= row.effective_due_at:
            lock_at_deadline_locked(response, now=now)
            if row.state in ("scheduled", "open"):
                row.state, row.version = "overdue", row.version + 1
                row.save()


def request_activation(*, event_id, actor, stage_form_id, data):
    from .work_models import StageActivationJob
    from .trigger_service import resolve_participant, trigger_at
    # A preview has no command receipt, audit or activation side effect.
    if data["preview"]:
        event = event_authority.get_event(actor, event_id, "edit_details")
        definition = EventStageForm.objects.get(pk=stage_form_id, event=event)
        require(definition.version == data["expected_version"], "stale_version")
        return {"preview": True, "eligible_participant_ids": [owner_id for owner_id in data["participant_ids"]
            if trigger_at(definition, resolve_participant(event=event, owner_id=owner_id)) is not None]}
    with command(event_id=event_id, actor=actor, data=data, action=f"stage.activate:{stage_form_id}",
        permission="edit_details", account_ids=tuple(data["participant_ids"])) as ctx:
        if ctx.replay:
            return ctx.replay
        definition = EventStageForm.objects.select_for_update().get(pk=stage_form_id, event=ctx.event)
        ctx.cas(definition)
        require(data["confirmed"] is True and data["due_at"] > timezone.now(), "activation_confirmation_required")
        validate_definition(definition, ctx.event, ctx.actor)
        require(definition.state == "published", "stage_not_published")
        row = StageActivationJob.objects.create(event=ctx.event, stage_form=definition, actor=ctx.actor,
            operation_id=data["operation_id"], command_digest=ctx.digest, participant_ids=sorted(set(data["participant_ids"])),
            effective_due_at=data["due_at"], pinned_form_revision=definition.current_revision)
        ctx.audit("event.stage_form.activation_requested", definition, job_id=row.pk, participant_count=len(row.participant_ids))
        return ctx.finish(row, stage_form_id=definition.pk)


def process_activation_locked(*, job_id, event, locks, limit):
    from .work_models import StageActivationJob
    from .trigger_service import resolve_participant
    from .transactions import require_outer
    require_outer(locks, event)
    job = StageActivationJob.objects.select_for_update().select_related("stage_form").get(pk=job_id, event=event)
    if job.state != "pending":
        return
    # A queued command never preserves revoked authoring authority or stale forms.
    if (job.actor is None or not event_authority.can(job.actor, event, "edit_details")
            or job.effective_due_at <= timezone.now() or job.stage_form.state != "published"
            or job.pinned_form_revision_id != job.stage_form.current_revision_id):
        job.state, job.version = "cancelled", job.version + 1
        job.save()
        return
    selected = job.participant_ids[job.cursor:job.cursor + limit]
    require(set(selected) <= set(locks.account_ids), "owner_fence_required")
    for owner_id in selected:
        subject = resolve_participant(event=event, owner_id=owner_id)
        activate_locked(definition=job.stage_form, subject=subject, locks=locks, due_at=job.effective_due_at)
    job.cursor, job.version = job.cursor + len(selected), job.version + 1
    if job.cursor >= len(job.participant_ids):
        job.state = "completed"
    job.save()
