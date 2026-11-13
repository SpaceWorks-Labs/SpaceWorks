"""What was made or machined for an event: the rows, and the totals the event page and the report share.

Read-only. One row per linked session or service request: the machine type, the person, minutes, the
consumables used (usage entries of a job), the member's charge as it stands, and the organiser's latest
cost decision. Totals add up minutes, consumables by pool and unit, and charges and approved amounts per
currency (never across currencies).
"""
from collections import defaultdict
from decimal import Decimal

from .machine_use_costs import latest_decision
from .models_machine_use import MachineEventCostApproval, MachineEventLink


def _consumed(entry):
    return entry.consumed_quantity or entry.consumed_grams or Decimal("0")


PAYMENT_KIND = {"session": "machine_session", "request": "machine_service_request", "booking": "booking"}


def _kind(link):
    return "session" if link.session_id else "booking" if link.booking_id else "request"


def _charges(links):
    from apps.payments.models import Payment
    wanted = defaultdict(set)
    for link in links:
        wanted[PAYMENT_KIND[_kind(link)]].add(link.session_id or link.service_request_id or link.booking_id)
    found = {}
    for kind, ids in wanted.items():
        for pay in Payment.objects.filter(subject_type=kind, subject_id__in=ids):
            found[(kind, pay.subject_id)] = pay
    return found


def rows_for(event):
    from apps.machines import sessions_state as state
    from apps.machines.models import MachineUsageEntry
    links = list(MachineEventLink.objects.filter(event=event).select_related(
        "machine_type", "session__machine", "session__member", "service_request__member",
        "service_request__requester", "booking__space", "booking__member").prefetch_related("cost_approvals").order_by("-created_at", "-id"))
    charges = _charges(links)
    usage = defaultdict(list)
    request_ids = [link.service_request_id for link in links if link.service_request_id]
    for entry in MachineUsageEntry.objects.filter(service_request_id__in=request_ids).select_related("consumable_pool"):
        usage[entry.service_request_id].append(entry)
    from apps.machines.consumable_usage import event_consumables
    profile = event_consumables(request_ids)  # decision 341: the type's profile actuals, not restating the ledger
    rows = []
    for link in links:
        if link.booking_id:
            item, who = link.booking, link.booking.member
            kind, title = "booking", link.booking.space.name
            minutes = max(int((item.ends_at - item.starts_at).total_seconds() // 60), 0)
            consumables = []
        elif link.session_id:
            item, who = link.session, link.session.member
            kind, title = "session", link.session.machine.name
            minutes = state.effective_minutes(item) if item.ended_at else 0
            consumables = []
        else:
            item = link.service_request
            who = item.member or item.requester
            kind, title = "request", item.title
            entries = usage.get(item.pk, [])
            minutes = sum(entry.duration_minutes for entry in entries)
            consumables = [{"label": entry.consumable_pool.material if entry.consumable_pool_id else "",
                            "unit": entry.metering_unit, "quantity": str(_consumed(entry))}
                           for entry in entries if _consumed(entry) > 0] + profile.get(item.pk, [])
        pay = charges.get((PAYMENT_KIND[kind], item.pk))
        decision = latest_decision(link)
        rows.append({
            "link_id": link.pk, "kind": kind, "subject_id": item.pk, "title": title,
            "machine_type": link.machine_type.name, "person_id": getattr(who, "pk", None), "person": getattr(who, "display_name", "") or "",
            "minutes": minutes, "consumables": consumables, "source": link.source,
            "created_at": link.created_at,
            "charge": {"amount": str(pay.amount), "currency": pay.currency, "status": pay.status} if pay else None,
            "cost_decision": decision.decision if decision else None,
        })
    return rows


def totals_for(rows):
    by_unit, charged, approved = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
    for row in rows:
        for item in row["consumables"]:
            by_unit[(item["label"], item["unit"])] += Decimal(item["quantity"])
        charge = row["charge"]
        if charge:
            charged[charge["currency"]] += Decimal(charge["amount"])
            if row["cost_decision"] == MachineEventCostApproval.Decision.APPROVED:
                approved[charge["currency"]] += Decimal(charge["amount"])
    return {
        "sessions": sum(1 for row in rows if row["kind"] == "session"),
        "bookings": sum(1 for row in rows if row["kind"] == "booking"),
        "requests": sum(1 for row in rows if row["kind"] == "request"),
        "minutes": sum(row["minutes"] for row in rows),
        "consumables": [{"label": label, "unit": unit, "quantity": str(total)}
                        for (label, unit), total in sorted(by_unit.items())],
        "charged": {code: str(total) for code, total in sorted(charged.items())},
        "approved_to_event": {code: str(total) for code, total in sorted(approved.items())},
    }
