"""Custom check-in lists (X45, lane L21a): swag, lunch, a workshop; online only in v1.

A list scan is its own append-only row. It NEVER marks attendance, changes a
registration or touches evidence. Who may collect, and how often:
- only confirmed people (registered or attended); with "after entry", only those checked in;
- an add-on list admits the buyer of that add-on on a PAID order, once per unit bought (L6);
- any other list admits each person `per_person` times.
An archived list is read-only until it is restored.

Parity E-B5 (D22) adds: list order, restore, a 60-second scan undo (the scan row stays, marked undone), a
waitlist override with the same rule as entry (a confirmed guest passes; a waitlisted guest needs an explicit
override; pending and declined guests never pass), eligible/collected counts, and a minor's guardian-consent
re-check on every collection (the same `require_minor_clearance` entry check-in makes, decision 291).
"""
from django.utils.translation import gettext
from datetime import timedelta

from django.db.models import Max, Sum
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
UNDO_WINDOW = timedelta(seconds=60)
REFUSALS = {"not_confirmed": "This person has no confirmed place.",
            "waitlisted": "This person is on the waitlist. Use override to let them collect.",
            "entry_required": "Check this person in at the door first.",
            "not_eligible": "This person did not buy this add-on.",
            "already_collected": "Already collected everything this person may collect."}


def require_feature(event):
    if not feature_enabled(event.makerspace, FEATURE):
        fail("not_found", gettext("Not found."), status=404)


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
    return EventCheckInListScan.objects.filter(checkin_list=checkin_list, registration=registration,
                                               undone_at__isnull=True).count()


def eligibility(checkin_list, registration, *, override=False):
    """(allowed, used, reason) -- reason is None when one more collection is allowed.

    A waitlisted guest is refused (`waitlisted`) until staff pass `override=True`, as at the entry desk.
    """
    allowed, taken = allowance(checkin_list, registration), used(checkin_list, registration)
    if registration.status == "waitlisted" and not override:
        return allowed, taken, "waitlisted"
    if registration.status not in CONFIRMED and registration.status != "waitlisted":
        return allowed, taken, "not_confirmed"
    if checkin_list.after_entry and registration.status != "attended":  # an override never skips the door
        return allowed, taken, "entry_required"
    if allowed <= 0:
        return allowed, taken, "not_eligible"
    if taken >= allowed:
        return allowed, taken, "already_collected"
    return allowed, taken, None


def _validate(checkin_list):
    if not checkin_list.name.strip():
        fail("invalid_name", gettext("Name the list."), status=400)
    if not 1 <= checkin_list.per_person <= 20:
        fail("invalid_per_person", gettext("Allow 1 to 20 collections per person."), status=400)
    if checkin_list.addon_id and checkin_list.addon.event_id != checkin_list.event_id:
        fail("not_found", gettext("Not found."), status=404)


def _check_quota(event):
    from apps.managed_hosting.extra_quotas import check_scoped_quota  # the `checkin_lists` limit: per event
    live = EventCheckInList.objects.filter(event=event, archived_at__isnull=True).count()
    check_scoped_quota(event.makerspace, "checkin_lists", live)


@event_write(permission="manage_registrations")
def create(event, *, actor, data):
    require_feature(event)
    row = EventCheckInList(makerspace=event.makerspace, event=event, created_by=actor,
                           **{key: data[key] for key in ("name", "kind", "after_entry", "per_person") if key in data})
    if data.get("addon_id"):
        from .models_addons import EventAddon
        row.addon = get_object_or_404(EventAddon, pk=data["addon_id"], event=event)
    _validate(row)
    _check_quota(event)
    row.position = (EventCheckInList.objects.filter(event=event).aggregate(top=Max("position"))["top"] or 0) + 1
    row.save()
    audit.record(actor, "event.checkin_list.created", makerspace=event.makerspace, target=row,
                 meta={"event_id": event.pk, "list_id": row.pk, "after_entry": row.after_entry,
                       "addon_id": row.addon_id})
    return row


@event_write(permission="manage_registrations")
def update(event, *, actor, list_id, data):
    require_feature(event)
    row = get_object_or_404(EventCheckInList.objects.select_for_update(), pk=list_id, event=event)
    if data.get("restore") and row.archived_at:
        _check_quota(event)
        row.archived_at = None
        row.save()
        audit.record(actor, "event.checkin_list.restored", makerspace=event.makerspace, target=row,
                     meta={"event_id": event.pk, "list_id": row.pk})
        return row
    if row.archived_at:
        fail("list_archived", gettext("An archived list is read-only."))
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


@event_write(permission="manage_registrations")
def reorder(event, *, actor, ordered_ids):
    """Set the desk order. Every open list of the event must be named once; archived ones keep their place."""
    require_feature(event)
    rows = {row.pk: row for row in EventCheckInList.objects.select_for_update().filter(event=event)}
    live = {pk for pk, row in rows.items() if row.archived_at is None}
    if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != live:
        fail("invalid_order", gettext("Name every open list exactly once."), status=400)
    for position, pk in enumerate(ordered_ids, start=1):
        if rows[pk].position != position:
            rows[pk].position = position
            rows[pk].save(update_fields=["position"])
    audit.record(actor, "event.checkin_list.reordered", makerspace=event.makerspace, target=event,
                 meta={"event_id": event.pk, "count": len(ordered_ids)})
    return [rows[pk] for pk in ordered_ids]


@event_write(permission="check_in")
def scan(event, *, actor, list_id, registration_id=None, token=None, operation_id, override=False):
    require_feature(event)
    row = get_object_or_404(EventCheckInList.objects.select_for_update(), pk=list_id, event=event)
    if row.archived_at:
        fail("list_archived", gettext("An archived list is read-only."))
    replay = EventCheckInListScan.objects.filter(checkin_list=row, operation_id=operation_id).first()
    if replay is not None:
        return replay, eligibility(row, replay.registration, override=override)
    lookup = {"pk": registration_id} if registration_id else {"checkin_token": token}
    registration = get_object_or_404(EventRegistration.objects.select_for_update(), event=event, **lookup)
    if registration.member_id:  # consent that lapsed after registration stops collection too (decision 291)
        from apps.makerspaces.minors_guard import require_minor_clearance
        require_minor_clearance(registration.member, event.makerspace, "event")
    allowed, taken, reason = eligibility(row, registration, override=override)
    if reason:
        fail(reason, REFUSALS[reason], fields={"allowed": [str(allowed)], "used": [str(taken)]})
    scan_row = EventCheckInListScan.objects.create(makerspace=event.makerspace, checkin_list=row,
                                                   registration=registration, operation_id=operation_id, actor=actor)
    audit.record(actor, "event.checkin_list.scanned", makerspace=event.makerspace, target=scan_row,
                 meta={"event_id": event.pk, "list_id": row.pk, "registration_id": registration.pk})
    if registration.status == "waitlisted":
        audit.record(actor, "event.checkin_list.override", makerspace=event.makerspace, target=scan_row,
                     meta={"event_id": event.pk, "list_id": row.pk, "registration_id": registration.pk})
    return scan_row, (allowed, taken + 1, None)


@event_write(permission="check_in")
def undo(event, *, actor, list_id, scan_id):
    """Undo one collection within 60 seconds of it. The row stays as evidence and stops counting."""
    require_feature(event)
    row = get_object_or_404(EventCheckInList.objects.select_for_update(), pk=list_id, event=event)
    if row.archived_at:
        fail("list_archived", gettext("An archived list is read-only."))
    scan_row = get_object_or_404(EventCheckInListScan.objects.select_for_update(), pk=scan_id, checkin_list=row)
    if scan_row.undone_at is not None:
        fail("already_undone", gettext("This collection was already undone."))
    if timezone.now() - scan_row.scanned_at > UNDO_WINDOW:
        fail("undo_window_closed", gettext("A collection can only be undone within a minute."))
    scan_row.undone_at, scan_row.undone_by = timezone.now(), actor
    scan_row.save(update_fields=["undone_at", "undone_by"])
    audit.record(actor, "event.checkin_list.scan_undone", makerspace=event.makerspace, target=scan_row,
                 meta={"event_id": event.pk, "list_id": row.pk, "registration_id": scan_row.registration_id})
    return scan_row


def counts(row):
    """(eligible, collected, people): who may collect, collections so far, and distinct people who did."""
    live = row.scans.filter(undone_at__isnull=True)
    people = live.values("registration").distinct().count()
    regs = EventRegistration.objects.filter(event_id=row.event_id,
                                            status__in=("attended",) if row.after_entry else CONFIRMED)
    if row.addon_id is None:
        return regs.count(), live.count(), people
    return sum(1 for reg in regs if allowance(row, reg) > 0), live.count(), people


def project(row):
    eligible, collected, people = counts(row)
    return {"id": row.pk, "event_id": row.event_id, "name": row.name, "kind": row.kind, "after_entry": row.after_entry,
            "addon_id": row.addon_id, "addon_name": row.addon.name if row.addon_id else None,
            "per_person": row.per_person, "archived": row.archived_at is not None, "archived_at": row.archived_at,
            "position": row.position, "eligible": eligible, "collected": collected, "collected_people": people}
