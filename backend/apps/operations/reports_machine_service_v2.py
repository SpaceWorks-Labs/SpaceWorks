"""Service outcomes bucketed on their own lifecycle timestamps."""

from collections import defaultdict
from decimal import Decimal

from django.db.models.functions import Coalesce

from apps.machines.models import ServiceRequestConsumption
from .reports_common import apply_range, period_expression
from .reports_machine_common import measured_service_hours, requests, result, spaces
from .reports_machine_facts import service_facts

FIELDS = (
    "period", "row_kind", "submitted", "accepted", "in_progress", "completed", "collected", "rejected", "failed", "cancelled",
    "machine_id", "machine_name", "machine_type", "request_count", "completed_count", "failed_count",
    "completed_hours", "failed_partial_hours", "total_recorded_service_hours", "failure_rate",
    "measurement", "product_id", "product_label", "completed_amount", "failed_partial_amount", "total_used",
    "outcome", "failed_count_amount", "failed_grams_amount",
)


def build_machine_service(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "machine_service"), actor):
        groups = {}
        submissions = apply_range(requests(space, scope), "created_at", date_range).annotate(
            period=period_expression("created_at", grain, makerspace=space),
        ).values("makerspace_id", "period", "status", "assigned_machine_id", "assigned_machine__name", "assigned_machine__machine_type__name")
        for source in submissions.iterator():
            period = source["period"].date().isoformat()
            status = groups.setdefault((source["makerspace_id"], period, "status"), {**_status(period), "makerspace_id": source["makerspace_id"]})
            status["submitted"] += 1
            if source["status"] in status:
                status[source["status"]] += 1
            if source["assigned_machine_id"]:
                row = _machine(groups, source["makerspace_id"], period, source["assigned_machine_id"], source["assigned_machine__name"], source["assigned_machine__machine_type__name"])
                row["request_count"] += 1
        for source in service_facts(space, scope, date_range, grain):
            if source["assigned_machine_id"] is None:
                continue
            period = source["period"].date().isoformat()
            row = _machine(groups, source["makerspace_id"], period, source["assigned_machine_id"], source["assigned_machine__name"], source["assigned_machine__machine_type__name"])
            failed = source["status"] == "failed"
            row["failed_count" if failed else "completed_count"] += 1
            row["failed_partial_hours" if failed else "completed_hours"] += measured_service_hours(source)
        for row in groups.values():
            if row["row_kind"] == "machine":
                terminal = row["completed_count"] + row["failed_count"]
                row["total_recorded_service_hours"] = row["completed_hours"] + row["failed_partial_hours"]
                row["failure_rate"] = round(row["failed_count"] * 100 / terminal, 2) if terminal else None
            rows.append(row)
        consumption = _consumption(space, scope, date_range, grain)
        rows.extend(consumption)
        failed_usage = defaultdict(Decimal)
        for row in consumption:
            failed_usage[(row["period"], row["machine_id"], row["measurement"])] += row["failed_partial_amount"]
        for machine in groups.values():
            if machine["row_kind"] != "machine" or not machine["failed_count"]:
                continue
            # Carry failure consumption on the machine row. Repeating failed_count
            # on a second summary row would double a scheduled count threshold.
            machine["failed_count_amount"] = failed_usage[(machine["period"], machine["machine_id"], "count")]
            machine["failed_grams_amount"] = failed_usage[(machine["period"], machine["machine_id"], "grams")]
    rows.sort(key=lambda r: (r["makerspace_id"], r["period"], r["row_kind"], r.get("machine_id") or 0, r.get("product_id") or 0, r.get("measurement") or ""))
    return result(FIELDS, rows, makerspace_id, limit, definition="Status counts are current outcomes of submissions in each period; failure rate is failed / (completed + failed) at terminal time, as percent.")


def _status(period):
    return {"period": period, "row_kind": "status", **dict.fromkeys(("submitted", "accepted", "in_progress", "completed", "collected", "rejected", "failed", "cancelled"), 0)}


def _machine(groups, space_id, period, machine_id, name, machine_type):
    return groups.setdefault((space_id, period, "machine", machine_id), {
        "makerspace_id": space_id, "period": period, "row_kind": "machine", "machine_id": machine_id,
        "machine_name": name, "machine_type": machine_type,
        "request_count": 0, "completed_count": 0, "failed_count": 0,
        "completed_hours": Decimal(0), "failed_partial_hours": Decimal(0),
    })


def _consumption(space, scope, date_range, grain):
    qs = ServiceRequestConsumption.objects.filter(service_request__in=requests(space, scope)).order_by()
    qs = qs.annotate(terminal_at=Coalesce("service_request__completed_at", "service_request__failed_at"))
    qs = apply_range(qs.filter(terminal_at__isnull=False), "terminal_at", date_range)
    groups = {}
    for source in qs.annotate(period=period_expression("terminal_at", grain, makerspace=space)).values(
        "service_request__makerspace_id", "period", "service_request__assigned_machine_id", "service_request__assigned_machine__name",
        "service_request__assigned_machine__machine_type__name", "measurement", "product_id", "label", "outcome", "quantity",
    ).iterator():
        period = source["period"].date().isoformat()
        key = (period, source["service_request__assigned_machine_id"], source["measurement"], source["product_id"], source["label"], source["service_request__makerspace_id"])
        row = groups.setdefault(key, {
            "makerspace_id": source["service_request__makerspace_id"], "period": period, "row_kind": "consumption",
            "machine_id": key[1], "machine_name": source["service_request__assigned_machine__name"],
            "machine_type": source["service_request__assigned_machine__machine_type__name"],
            "measurement": source["measurement"], "product_id": source["product_id"], "product_label": source["label"],
            "completed_amount": Decimal(0), "failed_partial_amount": Decimal(0),
        })
        row["failed_partial_amount" if source["outcome"] == "failed" else "completed_amount"] += source["quantity"]
    for row in groups.values():
        row["total_used"] = row["completed_amount"] + row["failed_partial_amount"]
    return list(groups.values())
