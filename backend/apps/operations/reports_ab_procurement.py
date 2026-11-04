"""Procurement cohorts, spend by kind/item, and receipt lead-time histogram."""

from decimal import Decimal

from apps.operations.reports_ab_common import dated, histogram, hours, result, spaces
from apps.procurement.models import ToBuyItem


FIELDS = ("period", "kind", "status", "item_id", "item_name", "lead_time_bucket", "currency", "items", "units",
          "estimated_total", "actual_total", "received_items", "inventoried_items", "order_hours",
          "order_samples", "receive_hours", "receive_samples", "average_order_hours", "average_receive_hours", "last_activity_at")


def build_procurement_performance(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    from apps.accounts import rbac
    from apps.machines import role_scope
    from apps.makerspaces.platform import module_enabled
    from django.db.models import Q
    records = []
    from apps.makerspaces.platform import feature_enabled
    for space in spaces(makerspace_id, "inventory.tobuy|machines.tobuy"):
        groups = {}
        # Each stream follows its own parent's To-Buy switch (#97, C-9).
        allowed = Q(kind="hardware") if feature_enabled(space, "inventory.tobuy") else Q(pk__in=[])
        if (actor is not None and feature_enabled(space, "machines.tobuy") and module_enabled(space, "printing")
                and rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk)):
            scope = role_scope.manage_scope_for(actor, space.pk)
            allowed |= Q(kind="printing") & role_scope.scope_q_for(scope, type_id_paths=("machine_type_id",))
        qs = dated(ToBuyItem.objects.filter(allowed, makerspace=space), "created_at", space, date_range, grain)
        for item in qs.iterator():
            lead = hours(item.ordered_at, item.received_at) if item.ordered_at and item.received_at else None
            key = (item.report_period.date(), item.kind, item.status, item.name,
                   histogram(lead) if lead is not None else "unknown")
            # No recorded currency exists, so even matching item labels cannot justify
            # combining monetary values. Keep each purchase's unknown-currency amount separate.
            key = (*key, item.pk)
            row = groups.setdefault(key, dict(makerspace_id=space.pk, period=key[0], kind=key[1], status=key[2],
                item_id=item.pk, item_name=key[3], lead_time_bucket=key[4], currency="unknown", items=0, units=0,
                estimated_total=None, actual_total=None, received_items=0, inventoried_items=0,
                order_hours=0, order_samples=0, receive_hours=0, receive_samples=0, last_activity_at=item.updated_at))
            row["items"] += 1
            row["units"] += item.quantity
            # ToBuyItem records no currency. Preserve that uncertainty instead of guessing
            # from a current gateway or membership plan (neither is the transaction's basis).
            for source, target in (("estimated_unit_cost", "estimated_total"), ("actual_unit_cost", "actual_total")):
                value = getattr(item, source)
                if value is not None:
                    row[target] = (row[target] or Decimal(0)) + value * item.quantity
            row["received_items"] += int(item.received_at is not None)
            row["inventoried_items"] += int(item.moved_to_inventory_at is not None)
            if item.ordered_at:
                row["order_hours"] += hours(item.created_at, item.ordered_at)
                row["order_samples"] += 1
            if lead is not None:
                row["receive_hours"] += lead
                row["receive_samples"] += 1
        for row in groups.values():
            for kind in ("order", "receive"):
                row[f"average_{kind}_hours"] = (round(row[f"{kind}_hours"] / row[f"{kind}_samples"], 2)
                                                 if row[f"{kind}_samples"] else None)
            records.append(row)
    records.sort(key=lambda row: (row["period"], -row["units"], row["item_name"]))
    return result(FIELDS, records, makerspace_id, limit,
        meta={"limitations": "Procurement prices have no recorded currency. Unknown-currency amounts stay per purchase and cannot form spend totals. Printing rows require machine authority."})
