"""Scheduled archive and purge, with reminders, cancellable (#185 item 4).

An ACTIVE (or paused) space gets an ``archive_on`` moment; when it passes, the space is
archived through the existing ``archive_requests.direct_archive`` (so the archival-money
impact, the two-key request auto-approval and their mail all still apply) and its purge
becomes due ``purge_grace_days`` later. An already ARCHIVED space gets only the purge.
The purge runs through the existing ``lifecycle.purge``. Both run as the superadmin who
scheduled them, re-validated at run time: if that account is no longer a live platform
superadmin the step is held and audited once, never run as nobody.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.lifecycle_authority import require_platform_superadmin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable

from .errors import SpaceControlConflict
from .models import SpaceControlState
from .services_access import locked_space, locked_state
from .write_policy import control_context

ACTIVE = Makerspace.LifecycleState.ACTIVE
SUSPENDED = Makerspace.LifecycleState.SUSPENDED


def is_archived(space):
    """Archived = a soft-deleted space whose lifecycle is otherwise active."""
    return space.lifecycle_state == ACTIVE and not is_servable(space)


def _clean(grace_days, note):
    if type(grace_days) is not int or not 1 <= grace_days <= 3650:
        raise ValidationError({"purge_grace_days": "Use 1 to 3650 days."})
    note = str(note or "").strip()
    if len(note) > 500:
        raise ValidationError({"note": "Use at most 500 characters."})
    return note


def schedule(actor, makerspace_id, *, archive_on=None, purge_grace_days=90, note=""):
    require_platform_superadmin(actor)
    note = _clean(purge_grace_days, note)
    now = timezone.now()
    with transaction.atomic(), control_context():
        space = locked_space(makerspace_id)
        state = locked_state(space)
        if state.has_schedule:
            raise SpaceControlConflict("schedule_exists", "This space already has a schedule. Cancel it first.")
        if is_archived(space):
            if archive_on is not None:
                raise ValidationError({"archive_on": "This space is already archived; only its purge can be scheduled."})
            state.archive_on, state.purge_due_at = None, now + timedelta(days=purge_grace_days)
        elif is_servable(space) or space.lifecycle_state == SUSPENDED:
            if archive_on is None or archive_on <= now:
                raise ValidationError({"archive_on": "Choose a future date and time for the archive."})
            state.archive_on, state.purge_due_at = archive_on, None
        else:
            raise SpaceControlConflict("space_not_active", "This space is being imported and cannot be scheduled.")
        state.purge_grace_days, state.schedule_note = purge_grace_days, note
        state.scheduled_by, state.scheduled_at, state.reminders_sent = actor, now, []
        state.save()
        audit.record(actor, "space_control.schedule_set", makerspace=space, target=space, meta={
            "archive_on": state.archive_on.isoformat() if state.archive_on else None,
            "purge_due_at": state.purge_due_at.isoformat() if state.purge_due_at else None,
            "purge_grace_days": purge_grace_days,
        })
        from .schedule_mail import schedule_set_mail
        schedule_set_mail(space, state)
    return space


def cancel(actor, makerspace_id):
    require_platform_superadmin(actor)
    with transaction.atomic(), control_context():
        space = locked_space(makerspace_id)
        state = locked_state(space)
        if not state.has_schedule:
            raise SpaceControlConflict("no_schedule", "This space has no scheduled archive or purge.")
        _clear(state)
        audit.record(actor, "space_control.schedule_cancelled", makerspace=space, target=space, meta={})
        from .schedule_mail import schedule_cancelled_mail
        schedule_cancelled_mail(space)
    return space


def _clear(state):
    state.archive_on = state.purge_due_at = state.scheduled_at = state.scheduled_by = None
    state.schedule_note, state.reminders_sent = "", []
    state.save(update_fields=["archive_on", "purge_due_at", "scheduled_at", "scheduled_by", "schedule_note",
                              "reminders_sent", "updated_at"])


def _runner(state):
    """The scheduling superadmin, or None after auditing (once) why the step is held."""
    actor = state.scheduled_by
    try:
        require_platform_superadmin(actor)
        return actor
    except DjangoValidationError:
        if "blocked" not in state.reminders_sent:
            state.reminders_sent = [*state.reminders_sent, "blocked"]
            state.save(update_fields=["reminders_sent", "updated_at"])
            audit.record(None, "space_control.schedule_blocked", makerspace=state.makerspace,
                         target=state.makerspace, meta={"reason": "scheduler_not_active_superadmin"})
        return None


def _space_id(state_id):
    return SpaceControlState.objects.filter(pk=state_id).values_list("makerspace_id", flat=True).first()


def _locked_pair(state_id):
    """Lock order makerspace -> control state, as every other control takes them."""
    space_id = _space_id(state_id)
    if space_id is None:
        return None, None
    space = locked_space(space_id)
    state = SpaceControlState.objects.select_for_update().filter(pk=state_id).first()
    return space, state


def run_archive(state_id):
    with transaction.atomic(), control_context():
        space, state = _locked_pair(state_id)
        if state is None or state.archive_on is None or state.archive_on > timezone.now():
            return False
        actor = _runner(state)
        if actor is None:
            return False
        if space.lifecycle_state == SUSPENDED:
            from .services_access import _clear_suspension
            _clear_suspension(space, state)
        from apps.makerspaces.archive_requests import direct_archive
        archived = direct_archive(space, actor)
        state.refresh_from_db()
        state.archive_on = None
        state.purge_due_at = timezone.now() + timedelta(days=state.purge_grace_days)
        state.reminders_sent = []
        state.save(update_fields=["archive_on", "purge_due_at", "reminders_sent", "updated_at"])
        audit.record(actor, "space_control.scheduled_archive_ran", makerspace=archived, target=archived,
                     meta={"purge_due_at": state.purge_due_at.isoformat()})
        from .schedule_mail import archived_mail
        archived_mail(archived, state)
    return True


def run_purge(state_id):
    with transaction.atomic(), control_context():
        space, state = _locked_pair(state_id)
        if state is None or state.purge_due_at is None or state.purge_due_at > timezone.now():
            return False
        if not is_archived(space):
            # Unarchived (or paused) since: the purge no longer applies.
            _clear(state)
            audit.record(None, "space_control.schedule_cleared", makerspace=space, target=space,
                         meta={"reason": "space_not_archived"})
            return False
        actor = _runner(state)
        if actor is None:
            return False
        meta = {"makerspace_id": space.pk, "slug": space.slug}
        from apps.makerspaces import lifecycle
        # The control row cascades with the space inside the purge's own savepoint.
        lifecycle.purge(space, actor)
        audit.record(actor, "space_control.scheduled_purge_ran", makerspace=None, target=None, meta=meta)
    return True
