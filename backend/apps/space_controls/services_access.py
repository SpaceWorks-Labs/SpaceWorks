"""Suspend / unblock and read-only on / off: the only writers of those states (#185).

Every manual control requires an active platform superadmin and is audited in the
space. Automatic read-only (a managed-hosting trial that ended, or an overdue hosting
invoice under auto-enforcement, #187A) has no human actor: it is audited with a null
actor and its ``source``, and only a lift naming the same source may undo it.
Lock order: makerspace -> control state. Reasons are never copied into audit meta.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.lifecycle_authority import require_platform_superadmin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable

from . import notifications
from .errors import SpaceControlConflict
from .models import SpaceControlState
from .write_policy import control_context

REASON_MIN, REASON_MAX = 10, 500
SOURCE = SpaceControlState.ReadOnlySource
PAUSED_REASON = "This space is paused by the platform operator."


def clean_reason(value):
    text = str(value or "").strip()
    if not REASON_MIN <= len(text) <= REASON_MAX:
        raise ValidationError({"reason": f"Give a reason of {REASON_MIN} to {REASON_MAX} characters."})
    return text


def locked_space(makerspace_id):
    return Makerspace.objects.select_for_update().get(pk=makerspace_id)


def locked_state(space):
    state, _ = SpaceControlState.objects.get_or_create(makerspace=space)
    return SpaceControlState.objects.select_for_update().get(pk=state.pk)


def suspend(actor, makerspace_id, reason):
    require_platform_superadmin(actor)
    reason = clean_reason(reason)
    with transaction.atomic(), control_context():
        space = locked_space(makerspace_id)
        # Explicit state: the superadmin's admission makes a paused space "servable" to them.
        if space.lifecycle_state != Makerspace.LifecycleState.ACTIVE or not is_servable(space):
            raise SpaceControlConflict("space_not_active", "Only an active space can be paused.")
        state = locked_state(space)
        space.lifecycle_state = Makerspace.LifecycleState.SUSPENDED
        space.save(update_fields=["lifecycle_state", "updated_at"])
        state.suspended_at, state.suspension_reason, state.suspended_by = timezone.now(), reason, actor
        state.save(update_fields=["suspended_at", "suspension_reason", "suspended_by", "updated_at"])
        audit.record(actor, "space_control.suspended", makerspace=space, target=space,
                     meta={"read_only": state.read_only_at is not None})
        notifications.notify(space, "suspended")
    return space


def unsuspend(actor, makerspace_id):
    require_platform_superadmin(actor)
    with transaction.atomic(), control_context():
        space = locked_space(makerspace_id)
        if space.lifecycle_state != Makerspace.LifecycleState.SUSPENDED:
            raise SpaceControlConflict("space_not_suspended", "This space is not paused.")
        state = locked_state(space)
        _clear_suspension(space, state)
        audit.record(actor, "space_control.unsuspended", makerspace=space, target=space,
                     meta={"read_only": state.read_only_at is not None})
        notifications.notify(space, "unsuspended")
        from .held_mail import release_held_mail
        release_held_mail(space.pk)
    return space


def _clear_suspension(space, state):
    space.lifecycle_state = Makerspace.LifecycleState.ACTIVE
    space.save(update_fields=["lifecycle_state", "updated_at"])
    state.suspended_at, state.suspension_reason, state.suspended_by = None, "", None
    state.save(update_fields=["suspended_at", "suspension_reason", "suspended_by", "updated_at"])


def set_read_only(actor, makerspace_id, reason, *, source=SOURCE.MANUAL):
    """Turn read-only on. Returns the space, or None when an automatic source finds it
    already read-only (automatic enforcement is idempotent; a manual repeat is a 409)."""
    if source == SOURCE.MANUAL:
        require_platform_superadmin(actor)
        reason = clean_reason(reason)
    with transaction.atomic(), control_context():
        space = locked_space(makerspace_id)
        if not (is_servable(space) or space.lifecycle_state == Makerspace.LifecycleState.SUSPENDED):
            raise SpaceControlConflict("space_not_active", "Only an active or paused space can be made read-only.")
        state = locked_state(space)
        if state.read_only_at is not None:
            if source != SOURCE.MANUAL:
                return None
            raise SpaceControlConflict("space_already_read_only", "This space is already read-only.")
        state.read_only_at, state.read_only_reason = timezone.now(), reason
        state.read_only_source, state.read_only_by = source, actor
        state.save(update_fields=["read_only_at", "read_only_reason", "read_only_source", "read_only_by",
                                  "updated_at"])
        audit.record(actor, "space_control.read_only_enabled", makerspace=space, target=space,
                     meta={"source": source})
        notifications.notify(space, "read_only", reason=reason)
    return space


def lift_read_only(actor, makerspace_id, *, source=None):
    """Turn read-only off. A manual lift (``source=None``) needs the superadmin and lifts
    any source; an automatic lift only undoes its own source and is a no-op otherwise."""
    if source is None:
        require_platform_superadmin(actor)
    with transaction.atomic(), control_context():
        space = locked_space(makerspace_id)
        state = locked_state(space)
        if state.read_only_at is None or (source is not None and state.read_only_source != source):
            if source is not None:
                return None
            raise SpaceControlConflict("space_not_read_only", "This space is not read-only.")
        previous = state.read_only_source
        state.read_only_at, state.read_only_reason, state.read_only_source, state.read_only_by = None, "", "", None
        state.save(update_fields=["read_only_at", "read_only_reason", "read_only_source", "read_only_by",
                                  "updated_at"])
        audit.record(actor, "space_control.read_only_lifted", makerspace=space, target=space,
                     meta={"source": previous})
        notifications.notify(space, "read_only_lifted")
    return space
