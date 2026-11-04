"""Custom check-in lists (X45, lane L21a): swag, lunch, a workshop; online only in v1.

A list scan is its own append-only row. It NEVER marks attendance, changes a
registration or touches evidence. Who may collect, and how often:
- only confirmed people (registered or attended); with "after entry", only those checked in;
- an add-on list admits the buyer of that add-on on a PAID order, once per unit bought (L6);
- any other list admits each person `per_person` times.
An archived list is read-only.
"""
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .hackathons.admission_errors import fail
from .models import EventRegistration
from .models_checkin_lists import EventCheckInList, EventCheckInListScan
from .services_write_boundary import event_write

FEATURE = "events.checkin_lists"
CONFIRMED = ("registered", "attended")


def require_feature(event):
    if not feature_enabled(event.makerspace, FEATURE):
        fail("not_found", "Not found.", status=404)


def allowance(checkin_list, registration):
    if checkin_list.addon_id is None:
        return checkin_list.per_person
    if registration.member_id is None:
        return 0
    from .models_orders import EventOrder, EventOrderLine
    bought = EventOrderLine.objects.filter(
        kind=EventOrderLine.Kind.ADDON, addon_id=checkin_list.addon_id, order__event_id=checkin_list.event_id,
        order__status=EventOrder.Status.PAID, order__buyer_id=registration.member_id,
    ).aggregate(total=Sum("quantity"))["total"]
    return bought or 0


def used(checkin_list, registration):
    return EventCheckInListScan.objects.filter(checkin_list=checkin_list, registration=registration).count()


def eligibility(checkin_list, registration):
    """(allowed, used, reason) -- reason is None when one more collection is allowed."""
    allowed, taken = allowance(checkin_list, registration), used(checkin_list, registration)
    if registration.status not in CONFIRMED:
        return allowed, taken, "not_confirmed"
    if checkin_list.after_entry and registration.status != "attended":
        return allowed, taken, "entry_required"
    if allowed <= 0:
        return allowed, taken, "not_eligible"
    if taken >= allowed:
        return allowed, taken, "already_collected"
    return allowed, taken, None


def _validate(checkin_list):
    if not checkin_list.name.strip():
        fail("invalid_name", "Name the list.", status=400)
    if not 1 <= checkin_list.per_person <= 20:
        fail("invalid_per_person", "Allow 1 to 20 collections per person.", status=400)
    if checkin_list.addon_id and checkin_list.addon.event_id != checkin_list.event_id:
        fail("not_found", "Not found.", status=404)


@event_write(permission="manage_registrations")
def create(event, *, actor, data):
    require_feature(event)
    row = EventCheckInList(makerspace=event.makerspace, event=event, created_by=actor,
                           **{key: data[key] for key in ("name", "kind", "after_entry", "per_person") if key in data})
    if data.get("addon_id"):
        from .models_addons import EventAddon
        row.addon = get_object_or_404(EventAddon, pk=data["addon_id"], event=event)
    _validate(row)
    row.save()
    audit.record(actor, "event.checkin_list.created", makerspace=event.makerspace, target=row,
                 meta={"event_id": event.pk, "list_id": row.pk, "after_entry": row.after_entry,
                       "addon_id": row.addon_id})
    return row


@event_write(permission="manage_registrations")
def update(event, *, actor, list_id, data):
    require_feature(event)
    row = get_object_or_404(EventCheckInList.objects.select_for_update(), pk=list_id, event=event)
    if row.archived_at:
        fail("list_archived", "An archived list is read-only.")
    for key in ("name", "kind", "after_entry", "per_person"):
        if key in data:
            setattr(row, key, data[key])
    if data.get("archive"):
        row.archived_at = timezone.now()
    _validate(row)
    row.save()
    if row.archived_at:
        audit.record(actor, "event.checkin_list.archived", makerspace=event.makerspace, target=row,
                     meta={"event_id": event.pk, "list_id": row.pk})
    else:
        audit.record(actor, "event.checkin_list.updated", makerspace=event.makerspace, target=row,
                     meta={"event_id": event.pk, "list_id": row.pk})
    return row


@event_write(permission="check_in")
def scan(event, *, actor, list_id, registration_id=None, token=None, operation_id):
    require_feature(event)
    row = get_object_or_404(EventCheckInList.objects.select_for_update(), pk=list_id, event=event)
    if row.archived_at:
        fail("list_archived", "An archived list is read-only.")
    replay = EventCheckInListScan.objects.filter(checkin_list=row, operation_id=operation_id).first()
    if replay is not None:
        return replay, eligibility(row, replay.registration)
    lookup = {"pk": registration_id} if registration_id else {"checkin_token": token}
    registration = get_object_or_404(EventRegistration.objects.select_for_update(), event=event, **lookup)
    allowed, taken, reason = eligibility(row, registration)
    if reason:
        fail(reason, {"not_confirmed": "This person has no confirmed place.",
                      "entry_required": "Check this person in at the door first.",
                      "not_eligible": "This person did not buy this add-on.",
                      "already_collected": "Already collected everything this person may collect."}[reason],
             fields={"allowed": [str(allowed)], "used": [str(taken)]})
    scan_row = EventCheckInListScan.objects.create(makerspace=event.makerspace, checkin_list=row,
                                                   registration=registration, operation_id=operation_id, actor=actor)
    audit.record(actor, "event.checkin_list.scanned", makerspace=event.makerspace, target=scan_row,
                 meta={"event_id": event.pk, "list_id": row.pk, "registration_id": registration.pk})
    return scan_row, (allowed, taken + 1, None)


def project(row):
    return {"id": row.pk, "event_id": row.event_id, "name": row.name, "kind": row.kind, "after_entry": row.after_entry,
            "addon_id": row.addon_id, "addon_name": row.addon.name if row.addon_id else None,
            "per_person": row.per_person, "archived": row.archived_at is not None, "archived_at": row.archived_at,
            "collected": row.scans.count()}
