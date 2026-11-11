"""Incident register workflow: report, triage, follow-up actions (decision 223 (k)).

`report` is the member and staff entry; `record_incident` is the trusted internal entry other
modules call (a guest's incident on their sponsor's record, decision 223 (f)) and it is a
silent no-op while the register is off. Every state change writes an audit row. Members may
only link what they own or can see (their own loan or booking, a machine, room or event of
the space); the person involved, sponsor, guest pass and repair links are staff fields.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record

from .models import Incident, IncidentAction
from .notify import staff_reported
from .scope import area_for, can_record, can_triage, incidents_on, require_incidents

LINKS = ("machine", "room", "event", "loan", "booking", "guest_pass")
STAFF_ONLY = ("involved_user", "involved_note", "sponsor_user", "repair_issue", "guest_pass", "area")
TRANSITIONS = {
    Incident.Status.REPORTED: {Incident.Status.TRIAGED, Incident.Status.IN_PROGRESS, Incident.Status.RESOLVED,
                               Incident.Status.CLOSED},
    Incident.Status.TRIAGED: {Incident.Status.IN_PROGRESS, Incident.Status.RESOLVED, Incident.Status.CLOSED},
    Incident.Status.IN_PROGRESS: {Incident.Status.RESOLVED, Incident.Status.CLOSED},
    Incident.Status.RESOLVED: {Incident.Status.IN_PROGRESS, Incident.Status.CLOSED},
    Incident.Status.CLOSED: set(),
}


def _same_space(space, name, row):
    owner = {"machine": "makerspace_id", "room": "makerspace_id", "event": "makerspace_id",
             "booking": "space.makerspace_id", "loan": "makerspace_id", "guest_pass": "makerspace_id"}[name]
    value = row
    for part in owner.split("."):
        value = getattr(value, part)
    if value != space.pk:
        raise ValidationError({name: gettext("Choose a record of this makerspace.")})


def _require_person(space, name, user):
    from apps.makerspaces.models import MakerspaceMembership
    if user is not None and not MakerspaceMembership.objects.filter(makerspace=space, user=user).exists():
        raise ValidationError({name: gettext("Choose a person who belongs to this makerspace.")})


def _validate(actor, space, fields, *, staff, trusted=False):
    for name in LINKS:
        row = fields.get(name)
        if row is None:
            continue
        _same_space(space, name, row)
        if not staff and name == "loan" and row.requester_id != actor.pk:
            raise PermissionDenied(gettext("You can only link your own loan."))
        if not staff and name == "booking" and row.member_id != actor.pk:
            raise PermissionDenied(gettext("You can only link your own booking."))
    if not staff:
        for name in STAFF_ONLY:
            if fields.get(name) not in (None, "", 0):
                raise PermissionDenied(gettext("Only staff can set this field."))
    if not trusted:
        for name in ("involved_user", "sponsor_user"):
            _require_person(space, name, fields.get(name))
    issue = fields.get("repair_issue")
    if issue is not None and issue.makerspace_id != space.pk:
        raise ValidationError({"repair_issue": gettext("Choose a repair of this makerspace.")})


def _meta(incident, **extra):
    return {"incident_id": incident.pk, "kind": incident.kind, "severity": incident.severity,
            "area": incident.area, **extra}


def _create(actor, space, fields, *, staff, trusted=False):
    _validate(actor, space, fields, staff=staff, trusted=trusted)
    links = {name: fields.get(name) for name in LINKS}
    area = area_for(**links, explicit=fields.get("area"))
    incident = Incident.objects.create(
        makerspace=space, reporter=actor, area=area, **{k: v for k, v in fields.items() if k != "area"})
    record(actor, "incident.reported", makerspace=space, target=incident,
           meta=_meta(incident, machine_id=incident.machine_id, event_id=incident.event_id,
                      sponsor_user_id=incident.sponsor_user_id))
    staff_reported(incident)
    return incident


@transaction.atomic
def report(actor, space, **fields):
    """A member's or staff member's report (an active member, or someone who reads the register)."""
    require_incidents(space)
    staff = can_record(actor, space)  # a read-only Technician reports as an ordinary member
    if not staff:
        from apps.machines.access import is_active_member
        if not is_active_member(actor, space.pk):
            raise PermissionDenied(gettext("Only members of this makerspace can report an incident."))
    return _create(actor, space, fields, staff=staff)


def record_incident(makerspace, *, title, actor=None, force_record=False, **fields):
    """Trusted internal entry (decision 223 (f)): record an incident from another module.

    Returns None, writing nothing, while `safety.incidents` is off, unless `force_record=True`
    (decision 226(f): only a sponsored guest's damage/loss uses it, so the record is retained while
    the register is off; it is not shown, because every read route and notice still 404s/skips).
    `fields` are the model's own (kind, severity, description, sponsor_user, involved_user, guest_pass, ...).
    """
    if not force_record and not incidents_on(makerspace):
        return None
    with transaction.atomic():
        return _create(actor, makerspace, {"title": title[:200], **fields}, staff=True, trusted=True)


@transaction.atomic
def update(actor, incident, **fields):
    incident = Incident.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=incident.pk)
    require_incidents(incident.makerspace)
    if not can_triage(actor, incident):
        raise PermissionDenied()
    _validate(actor, incident.makerspace, fields, staff=True)
    status = fields.pop("status", None)
    changed = []
    for name, value in fields.items():
        if getattr(incident, name) != value:
            setattr(incident, name, value)
            changed.append(name)
    if set(changed) & {*LINKS, "area"}:
        # Re-placed from its links, then re-checked: triage never moves an incident
        # into an area (or machine type) the actor does not read (API scoping audit).
        area = area_for(**{name: getattr(incident, name) for name in LINKS if name != "guest_pass"},
                        explicit=incident.area)
        if area != incident.area:
            incident.area = area
            changed.append("area")
        incident.save(update_fields=[*dict.fromkeys(changed), "updated_at"])
        if not can_triage(actor, incident):
            raise PermissionDenied()
    if status is not None and status != incident.status:
        if status not in TRANSITIONS[incident.status]:
            raise ValidationError({"status": gettext("This incident cannot move to that status.")})
        previous, incident.status = incident.status, status
        changed.append("status")
        if incident.triaged_by_id is None:
            incident.triaged_by = actor
            changed.append("triaged_by")
        if status == Incident.Status.CLOSED:
            incident.closed_at = timezone.now()
            changed.append("closed_at")
        record(actor, "incident.status_changed", makerspace=incident.makerspace, target=incident,
               meta=_meta(incident, from_status=previous, to_status=status))
    if changed:
        incident.save(update_fields=[*dict.fromkeys(changed), "updated_at"])
        record(actor, "incident.updated", makerspace=incident.makerspace, target=incident,
               meta=_meta(incident, fields=sorted(set(changed) - {"status", "closed_at", "triaged_by"})))
    return incident


@transaction.atomic
def add_action(actor, incident, *, description, assignee=None, due_date=None):
    incident = Incident.objects.select_related("makerspace").get(pk=incident.pk)
    require_incidents(incident.makerspace)
    if not can_triage(actor, incident):
        raise PermissionDenied()
    _require_person(incident.makerspace, "assignee_id", assignee)
    action = IncidentAction.objects.create(
        incident=incident, description=description, assignee=assignee, due_date=due_date, created_by=actor)
    record(actor, "incident.action_added", makerspace=incident.makerspace, target=action,
           meta={"incident_id": incident.pk, "action_id": action.pk, "assignee_id": getattr(assignee, "pk", None)})
    return action


@transaction.atomic
def set_action_done(actor, action, *, done):
    action = IncidentAction.objects.select_for_update(of=("self",)).select_related(
        "incident__makerspace").get(pk=action.pk)
    incident = action.incident
    require_incidents(incident.makerspace)
    if not can_triage(actor, incident):
        raise PermissionDenied()
    action.done_at, action.done_by = (timezone.now(), actor) if done else (None, None)
    action.save(update_fields=["done_at", "done_by"])
    record(actor, "incident.action_done", makerspace=incident.makerspace, target=action,
           meta={"incident_id": incident.pk, "action_id": action.pk, "done": bool(done)})
    return action
