"""Canonical hooks and recovery use the same stage-only state writer.

No admission, registration, attendance or financial status is changed here.
Call after canonical parents under the outer event/fence transaction.
"""
from types import SimpleNamespace
from django.utils import timezone
from apps.audit.services import record
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .trigger_service import trigger_at, schedule
from .transactions import require_outer, lock_stage_parents
from .notices import enqueue_locked

ORDER = {"application": 0, "shortlisted": 1, "accepted_rsvp": 2, "pre_event": 4, "post_event": 5}


def frozen_policy(row):
    values = {**{name: getattr(row.stage_form, name) for name in (
        "stage", "activation_point", "required", "missed_action", "blocked_actions", "lock_on_next_stage", "audience",
        "opening_mode", "opens_at", "opening_offset_seconds", "due_mode", "due_at", "due_after_seconds",
        "due_event_offset_seconds", "reminder_offsets")}, **row.policy_snapshot}
    from datetime import datetime
    for key in ("opens_at", "due_at"):
        if isinstance(values[key], str):
            values[key] = datetime.fromisoformat(values[key])
    return SimpleNamespace(**values)


def reached_rank(subject, now):
    from .milestone_models import EventStageMilestone
    rank = 0
    if EventStageMilestone.objects.filter(event=subject.event, member_id=subject.owner_member_id,
        kind="shortlisted", withdrawn_at__isnull=True).exists():
        rank = 1
    if subject.application:
        if subject.application.state in ("offered", "confirmed"):
            rank = 3 if subject.application.state == "confirmed" else 2
    elif subject.registration and subject.registration.status in ("registered", "attended"):
        rank = 3
    if subject.registration and subject.registration.status in ("registered", "attended"):
        if now >= subject.event.starts_at:
            rank = 4
        if now >= subject.event.ends_at:
            rank = 5
    return rank


def cancel_participant_locked(*, subject, locks, actor=None, reason_code="participation_cancelled"):
    require_outer(locks, subject.event)
    from apps.payments.event_payouts.errors import require
    require(subject.owner_member_id in locks.account_ids, "owner_fence_required")
    lock_stage_parents(event=subject.event, owner_ids=(subject.owner_member_id,))
    rows = StageFormAssignment.objects.select_for_update().filter(event=subject.event,
        owner_member_id=subject.owner_member_id).exclude(state="cancelled").order_by("pk")
    for row in rows:
        response = StageFormResponse.objects.select_for_update().filter(assignment=row).first()
        old = row.state
        row.state, row.cancelled_at, row.cancelled_by = "cancelled", timezone.now(), actor
        row.cancellation_reason_code, row.completed_response = reason_code, None
        row.version += 1
        if response:
            response.state = "locked" if response.current_submitted_revision_id else "withdrawn"
            response.locked_at = response.answer_locked_at = row.cancelled_at
            response.version += 1
            response.save()
        row.save()
        record(actor, "event.stage_form.cancelled", makerspace=subject.event.makerspace, target=row,
               meta={"assignment_id": row.pk, "old_state": old, "new_state": "cancelled", "reason_code": reason_code})
        enqueue_locked(row, "cancelled")


def reconcile_participant_locked(*, subject, locks, now=None):
    require_outer(locks, subject.event)
    lock_stage_parents(event=subject.event, owner_ids=(subject.owner_member_id,))
    now = now or timezone.now()
    if subject.event.status == "cancelled" or (
        subject.registration and subject.registration.status in ("cancelled", "rejected")) or (
        subject.application and subject.application.state in ("rejected", "withdrawn", "declined", "expired")):
        return cancel_participant_locked(subject=subject, locks=locks,
            reason_code="event_cancelled" if subject.event.status == "cancelled" else "participation_cancelled")
    reached = reached_rank(subject, now)
    for row in StageFormAssignment.objects.select_for_update().filter(event=subject.event,
        owner_member_id=subject.owner_member_id).exclude(state="cancelled").order_by("pk"):
        policy = frozen_policy(row)
        rank = 3 if policy.stage == "accepted_rsvp" and policy.activation_point == "rsvp" else ORDER[policy.stage]
        reviewed_rank = getattr(policy, "lock_suppressed_through_rank", -1)
        if policy.lock_on_next_stage and reached > max(rank, reviewed_rank) and row.next_stage_locked_at is None:
            response = StageFormResponse.objects.select_for_update().filter(assignment=row).first()
            row.next_stage_locked_at, row.version = now, row.version + 1
            row.save()
            from .response_workflow import lock_at_deadline_locked
            if response:
                lock_at_deadline_locked(response, now=now)
            record(None, "event.stage_form.next_stage_locked", makerspace=subject.event.makerspace, target=row,
                   meta={"assignment_id": row.pk})


def reschedule_event_locked(*, event, locks, actor=None):
    """G calls after incrementing event_date_revision, before its outer commit.

    Completed/locked responses stay closed. Extensions keep their reviewed delta.
    Invalid moved schedules refuse the outer date edit; no silent relocking.
    """
    require_outer(locks, event)
    lock_stage_parents(event=event, owner_ids=locks.account_ids)
    for row in StageFormAssignment.objects.select_for_update().filter(event=event,
        owner_member_id__in=locks.account_ids).exclude(state="cancelled").exclude(
            schedule_event_date_revision=event.event_date_revision).order_by("pk"):
        policy = frozen_policy(row)
        row.schedule_event_date_revision = event.event_date_revision
        if not (policy.opening_mode in ("event_start", "event_end") or policy.due_mode in ("event_start", "event_end")
                or policy.stage in ("pre_event", "post_event")):
            row.version += 1
            row.save(update_fields=["schedule_event_date_revision", "version"])
            record(actor, "event.stage_form.date_context_changed", makerspace=event.makerspace, target=row,
                   meta={"assignment_id": row.pk, "event_date_revision": event.event_date_revision, "absolute_deadline_unchanged": True})
            continue
        trigger = event.starts_at if policy.stage == "pre_event" else event.ends_at if policy.stage == "post_event" else row.triggered_at
        value = schedule(policy, subject=SimpleNamespace(event=event), triggered_at=trigger)
        extension = row.effective_due_at - row.base_due_at
        row.triggered_at, row.opens_at = trigger, value.opens_at
        row.base_due_at, row.effective_due_at = value.due_at, value.due_at + extension
        row.due_revision, row.version = row.due_revision + 1, row.version + 1
        row.save()
        record(actor, "event.stage_form.rescheduled", makerspace=event.makerspace, target=row,
               meta={"assignment_id": row.pk, "due_revision": row.due_revision, "event_date_revision": event.event_date_revision})
        enqueue_locked(row, "rescheduled")


def cancel_event_locked(*, event, locks, actor=None):
    from apps.payments.event_payouts.errors import require
    from .trigger_service import resolve_participant
    require_outer(locks, event)
    owners = set(StageFormAssignment.objects.filter(event=event).exclude(state="cancelled").values_list("owner_member_id", flat=True))
    require(owners <= set(locks.account_ids), "owner_fence_required")
    lock_stage_parents(event=event, owner_ids=owners)
    for owner_id in sorted(owners):
        cancel_participant_locked(subject=resolve_participant(event=event, owner_id=owner_id), locks=locks,
                                  actor=actor, reason_code="event_cancelled")
