"""Cross-source sections for the event/booking related-facts views (decision 216 item 13).

Registration, attendance, booking arrival, presence check-in and machine sessions are
INDEPENDENT facts. Each section here reads exactly one source, is gated by that
source's own module and staff authority, carries a ``source`` label, and never writes
or derives one fact from another. A section the actor may not see is omitted, never
returned empty, so absence cannot be read as "nothing happened".
"""

from django.db.models import Q
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled

PRESENCE_SOURCE = "presence.PresenceSession"
MACHINE_SOURCE = "machines.MachineSession"


def presence_available(actor, space):
    """The presence module's own gate plus its staff action (MANAGE_MEMBERS)."""
    from apps.presence.policy import require_enabled
    try:
        require_enabled(space)
    except NotFound:
        return False
    return rbac.can(actor, rbac.Action.MANAGE_MEMBERS, space.pk)


def _presence_overlapping(space, start, end):
    from apps.presence.models import PresenceSession
    # A session occupies [started_at, ended_at) once ended, else [started_at, expires_at).
    return PresenceSession.objects.filter(makerspace=space, started_at__lt=end).filter(
        Q(ended_at__isnull=False, ended_at__gt=start) | Q(ended_at__isnull=True, expires_at__gt=start))


def _person_withheld(space, account_id, sessions):
    """Existing display rules: names off, or an honoured personal opt-out, hide a person."""
    from apps.presence.models import PresencePreference
    from apps.presence.privacy import settings_for
    policy = settings_for(space)
    if not policy.show_names:
        return True
    if not policy.allow_personal_opt_out:
        return False
    hidden = PresencePreference.objects.filter(
        makerspace=space, account_id=account_id, hide_on_display=True).exists()
    return hidden or sessions.filter(account_id=account_id, hide_on_display=True).exists()


def presence_section(actor, space, start, end, *, event=None, person_id=None):
    """Counts only. A named person's own state is reported only if they are displayable."""
    if not presence_available(actor, space):
        return None
    rows = _presence_overlapping(space, start, end)
    section = {
        "source": PRESENCE_SOURCE,
        "window_start": start, "window_end": end,
        "sessions_overlapping": rows.count(),
        "distinct_people": rows.order_by().values("account_id").distinct().count(),
    }
    if event is not None:
        # The session's own link, written only by the live event-ticket hook.
        section["sessions_linked_to_event"] = rows.filter(event_registration__event=event).count()
    if person_id is not None:
        if _person_withheld(space, person_id, rows):
            section["subject_person_presence"] = "withheld"
        else:
            own = rows.filter(account_id=person_id).exists()
            section["subject_person_presence"] = "recorded" if own else "not_recorded"
    return section


def machine_available(actor, machine):
    """Machines module + sessions feature, MANAGE_MACHINES and per-type role reach."""
    from apps.machines import role_scope
    space = machine.makerspace
    if not (module_enabled(space, "machines") and feature_enabled(space, "machines.sessions")):
        return False
    if not rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk):
        return False
    return role_scope.covers_machine(actor, machine)


def machine_sessions_section(actor, machine, start, end, *, person_id=None):
    from apps.machines import sessions_state as state
    from apps.machines.models import MachineSession
    if machine is None or not machine_available(actor, machine):
        return None
    rows = list(MachineSession.objects.filter(
        makerspace_id=machine.makerspace_id, machine=machine, started_at__lt=end,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gt=start)).prefetch_related("amendments")
        .order_by("started_at", "pk"))
    sessions = [{
        "session_id": row.pk, "started_at": row.started_at, "ended_at": row.ended_at,
        "source": row.source, "minutes": state.effective_minutes(row),
        "by_subject_person": person_id is not None and state.effective_member_id(row) == person_id,
    } for row in rows]
    return {
        "source": MACHINE_SOURCE, "machine_id": machine.pk, "machine_name": machine.name,
        "window_start": start, "window_end": end,
        "sessions_overlapping": len(sessions), "sessions": sessions,
    }
