"""Machine use logged with an event (decision 342): counts per event, and one event's own rows.

* `machine-use-by-event` -- per event and machine type: sessions, service requests, machine minutes and
  consumable entries. Counts only, no person.
* `event-machine-use` -- one event's linked sessions and jobs (event staff, the event subject path); names a
  person, so identity-bearing.

Both read only links whose session or request sits on a machine or machine type the actor's role scope covers,
so a Machine Manager never sees another area's use. The event-side authority is the event's own
(`events.report_subject`); neither report touches money beyond counting the organiser's approvals.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.machines.models import MachineUsageEntry
from .report_types import ReportNotFound
from .reports_machine_common import machines, requests, result, space_ids, spaces
from .reports_machine_sessions import window

EVENT_FIELDS = ("event_id", "event_title", "machine_type", "sessions", "bookings", "requests", "machine_minutes",
                "consumable_entries", "approved_to_event")
USE_FIELDS = ("link_id", "kind", "subject_id", "title", "machine_type", "person_id", "person", "minutes",
              "consumable_entries", "charge_amount", "charge_currency", "charge_status", "cost_decision")


def _scoped_links(space, scope):
    from apps.events.models_machine_use import MachineEventLink  # events is separable: import on use
    return MachineEventLink.objects.filter(makerspace_id__in=space_ids(space)).filter(
        Q(session__machine__in=machines(space, scope)) | Q(service_request__in=requests(space, scope))
        | Q(booking__space__machine__in=machines(space, scope)))


def build_machine_use_by_event(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    from apps.events.models_machine_use import MachineEventCostApproval
    rows, now = [], timezone.now()
    for space, scope in spaces(makerspace_id, ("machines", "events"), actor):
        start, end = window(date_range, now)
        links = list(_scoped_links(space, scope).filter(created_at__gte=start, created_at__lte=end).select_related(
            "event", "machine_type", "session", "service_request", "booking").prefetch_related("cost_approvals"))
        entries = defaultdict(int)
        for pk in MachineUsageEntry.objects.filter(
                service_request__in=[link.service_request_id for link in links if link.service_request_id]
        ).filter(Q(consumed_quantity__gt=0) | Q(consumed_grams__gt=0)).values_list("service_request_id", flat=True):
            entries[pk] += 1
        from apps.machines.consumable_usage import event_consumables
        for pk, lines in event_consumables(link.service_request_id for link in links if link.service_request_id).items():
            entries[pk] += len(lines)  # decision 341: profile actuals that do not restate the pool ledger
        groups = {}
        for link in links:
            key = (link.makerspace_id, link.event_id, link.machine_type_id)
            group = groups.setdefault(key, {
                "makerspace_id": link.makerspace_id, "event_id": link.event_id, "event_title": link.event.title,
                "machine_type": link.machine_type.name, "sessions": 0, "bookings": 0, "requests": 0, "machine_minutes": 0,
                "consumable_entries": 0, "approved_to_event": 0})
            latest = link.cost_approvals.first()
            group["approved_to_event"] += int(bool(latest and latest.decision == MachineEventCostApproval.Decision.APPROVED))
            if link.booking_id:
                group["bookings"] += 1
            elif link.session_id:
                from apps.machines import sessions_state as state
                group["sessions"] += 1
                group["machine_minutes"] += state.effective_minutes(link.session) if link.session.ended_at else 0
            else:
                group["requests"] += 1
                group["consumable_entries"] += entries.get(link.service_request_id, 0)
        rows.extend(sorted(groups.values(), key=lambda g: (g["event_title"], g["machine_type"], g["event_id"])))
    return result(EVENT_FIELDS, rows, makerspace_id, limit)


def build_event_machine_use(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None, actor=None, **_kwargs):
    if subject_kind != "event" or makerspace_id is None:
        raise ReportNotFound()
    from apps.events.machine_use_summary import rows_for
    from apps.events.models import Event
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "events"), actor, identities=True):
        event = get_object_or_404(Event, makerspace=space, pk=subject_id)
        allowed = set(_scoped_links(space, scope).filter(event=event).values_list("pk", flat=True))
        for row in rows_for(event):
            if row["link_id"] not in allowed:
                continue
            charge = row["charge"] or {}
            rows.append({
                "link_id": row["link_id"], "kind": row["kind"], "subject_id": row["subject_id"], "title": row["title"],
                "machine_type": row["machine_type"], "person_id": row["person_id"], "person": row["person"],
                "minutes": row["minutes"], "consumable_entries": len(row["consumables"]),
                "charge_amount": Decimal(charge["amount"]) if charge else None,
                "charge_currency": charge.get("currency", ""), "charge_status": charge.get("status", ""),
                "cost_decision": row["cost_decision"] or ""})
    return result(USE_FIELDS, rows, makerspace_id, limit)
