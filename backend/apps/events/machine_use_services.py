"""Link a machine session or service request to an event, and record who changed it (decision 342).

Three writers, one audit trail (`machine_event.linked` / `changed` / `cleared`, with before and after):

* the requester, at submit or session start (`attach`, strict: an event they may not act for is refused);
* an adapter session (`attach_quiet`: ignored when not eligible, it never fails a session);
* the area manager, when accepting or handling the item (`manage`: set, change or clear), limited to
  Space Managers and Machine Managers within machine scope.

A link whose cost the organiser approved is locked: it cannot be changed or cleared until the approval is withdrawn.
The machines app calls only `attach`, `attach_quiet` and `manage`; it never imports an event model.
"""
from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit import services as audit

from .machine_use_eligibility import eligible_events, linkable_events
from .models_machine_use import MachineEventCostApproval, MachineEventLink


def subject_facts(subject):
    """(makerspace, machine_type, person, kwargs for the link) of a session, a service request or a booking."""
    from apps.bookings.models import Booking
    from apps.machines.models import MachineSession
    if isinstance(subject, Booking):
        space = subject.space
        machine_type = space.machine_type or (space.machine.machine_type if space.machine_id else None)
        if space.kind != "machine" or machine_type is None:
            raise ValidationError({"event_id": gettext("Only a machine-time booking can be logged for an event."),
                                   "code": "not_machine_booking"})
        return space.makerspace, machine_type, subject.member, {"booking": subject}
    if isinstance(subject, MachineSession):
        return subject.makerspace, subject.machine_type, subject.member, {"session": subject}
    queue_type = subject.queue.machine_type if subject.queue_id else subject.bucket.machine.machine_type
    return subject.makerspace, queue_type, (subject.member or subject.requester), {"service_request": subject}


def _meta(subject, link_kwargs, **extra):
    key = {"session": "session_id", "booking": "booking_id"}.get(next(iter(link_kwargs)), "service_request_id")
    return {key: subject.pk, **extra}


def current_link(subject):
    _space, _type, _person, kwargs = subject_facts(subject)
    return MachineEventLink.objects.select_related("event").filter(**kwargs).first()


def require_event_for(space, person, event_id):
    """The event a requester picked, or a 400 that never says whether an event they cannot see exists."""
    event = eligible_events(person, space).filter(pk=event_id).first()
    if event is None:
        raise ValidationError({"event_id": gettext("Choose one of your events."), "code": "event_not_eligible"})
    return event


def _create(subject, event, actor, source):
    space, machine_type, _person, kwargs = subject_facts(subject)
    link = MachineEventLink.objects.create(makerspace=space, event=event, machine_type=machine_type,
                                           source=source, **kwargs)
    audit.record(actor, "machine_event.linked", makerspace=space, target=link,
                 meta=_meta(subject, kwargs, event_id=event.pk, before_event_id=None, after_event_id=event.pk,
                            machine_type_id=machine_type.pk, source=source, link_id=link.pk))
    return link


def attach(subject, event_id, *, actor):
    """Requester path: strict. No event given means no link and no error."""
    if event_id in (None, ""):
        return None
    space, _type, person, _kwargs = subject_facts(subject)
    return _create(subject, require_event_for(space, person, event_id), actor, MachineEventLink.Source.REQUESTER)


def attach_quiet(subject, event_id):
    """Adapter path: only an event the session's member may act for is linked; anything else is ignored."""
    if event_id in (None, ""):
        return None
    try:
        space, _type, person, _kwargs = subject_facts(subject)
        event = eligible_events(person, space).filter(pk=int(event_id)).first()
        return _create(subject, event, None, MachineEventLink.Source.ADAPTER) if event else None
    except (TypeError, ValueError):
        return None


def may_manage(actor, subject):
    """Space Manager, or a Machine Manager whose scope covers the item's machine or machine type."""
    from apps.machines import access
    space, machine_type, _person, kwargs = subject_facts(subject)
    if "booking" in kwargs:
        from .machine_link_access import can_manage_machine_space
        return can_manage_machine_space(actor, subject.space) or access.can_create_machine(actor, space.pk, machine_type)
    machine = getattr(subject, "machine", None) or getattr(subject, "assigned_machine", None)
    if machine is not None and access.can_manage_machine(actor, machine):
        return True
    return access.can_create_machine(actor, space.pk, machine_type)


def _approved(link):
    latest = link.cost_approvals.first()
    return latest is not None and latest.decision == MachineEventCostApproval.Decision.APPROVED


@transaction.atomic
def manage(actor, subject, event_id):
    """Set, change or clear the event of one item; `event_id=None` clears. Returns the link or None."""
    if not may_manage(actor, subject):
        raise NotFound()
    space, _type, _person, kwargs = subject_facts(subject)
    link = MachineEventLink.objects.select_for_update().filter(**kwargs).first()
    before = link.event_id if link else None
    event = None
    if event_id is not None:
        event = linkable_events(space).filter(pk=event_id).first()
        if event is None:
            raise ValidationError({"event_id": gettext("Choose an open event of this makerspace."),
                                   "code": "event_not_linkable"})
    if before == (event.pk if event else None):
        return link
    if link is not None and _approved(link):
        raise ValidationError({"detail": gettext("The organiser approved this cost for the event; withdraw "
                                                 "the approval first."), "code": "cost_approved"})
    if link is None:
        return _create_as_manager(subject, event, actor)
    if event is None:
        MachineEventLink.objects.filter(pk=link.pk).delete()
        action, result = "machine_event.cleared", None
    else:
        MachineEventLink.objects.filter(pk=link.pk).update(event=event)
        action, result = "machine_event.changed", MachineEventLink.objects.get(pk=link.pk)
    audit.record(actor, action, makerspace=space, target=result or link,
                 meta=_meta(subject, kwargs, before_event_id=before, after_event_id=event.pk if event else None,
                            link_id=link.pk))
    return result


def _create_as_manager(subject, event, actor):
    return _create(subject, event, actor, MachineEventLink.Source.MANAGER)
