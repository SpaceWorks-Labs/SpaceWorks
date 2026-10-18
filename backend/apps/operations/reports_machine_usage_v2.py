"""Three deliberately separate hour measures, with no inferred person identity."""

from decimal import Decimal

from .reports_machine_common import hours, measured_service_hours, result, spaces
from .reports_machine_facts import booking_facts, manual_facts, service_facts

DIMENSIONS = ("period", "measure", "machine_id", "machine_name", "machine_type_id", "machine_type")
FIELDS = (*DIMENSIONS, "entries", "service_hours", "manual_hours", "booked_hours")
MEMBER_FIELDS = ("period", "member_id", "measure", "machine_type_id", "machine_type", "entries", "hours")


def usage_facts(space, scope, date_range, grain):
    for row in service_facts(space, scope, date_range, grain):
        yield {
            "makerspace_id": row["makerspace_id"],
            "period": row["period"].date().isoformat(), "measure": "service",
            "machine_id": row["assigned_machine_id"], "machine_name": row["assigned_machine__name"] or "Unassigned",
            "machine_type_id": row["assigned_machine__machine_type_id"] or row["queue__machine_type_id"],
            "machine_type": row["assigned_machine__machine_type__name"] or row["queue__machine_type__name"] or "Unknown",
            "member_id": row["member_id"], "hours": measured_service_hours(row),
        }
    for row in manual_facts(space, scope, date_range, grain):
        yield {
            "makerspace_id": row["machine__makerspace_id"],
            "period": row["period"].date().isoformat(), "measure": "manual",
            "machine_id": row["machine_id"], "machine_name": row["machine__name"],
            "machine_type_id": row["machine__machine_type_id"], "machine_type": row["machine__machine_type__name"],
            "member_id": row["member_id"], "hours": row["hours"],
        }
    for row in booking_facts(space, scope, date_range, grain):
        yield {
            "makerspace_id": row["space__makerspace_id"],
            "period": row["period"].date().isoformat(), "measure": "booked",
            "machine_id": None, "machine_name": "By machine type",
            "machine_type_id": row["space__machine_type_id"], "machine_type": row["space__machine_type__name"],
            "member_id": row["member_id"], "hours": hours(row["ends_at"] - row["starts_at"]),
        }


def build_machine_usage(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        groups = {}
        for fact in usage_facts(space, scope, date_range, grain):
            key = (fact["makerspace_id"], *(fact[field] for field in DIMENSIONS))
            target = groups.setdefault(key, {field: fact[field] for field in DIMENSIONS})
            target["entries"] = target.get("entries", 0) + 1
            target["hours"] = target.get("hours", Decimal(0)) + fact["hours"]
            target["makerspace_id"] = fact["makerspace_id"]
        rows.extend(groups.values())
    # Organization combination and exports request all inputs (limit=None), so a
    # tenant's local top five cannot hide another tenant's globally ranked machine.
    if limit is not None:
        rows = _top_five_series(rows)
    rows.sort(key=lambda r: (r["makerspace_id"], r["period"], r["measure"], -r["hours"], r["machine_id"] or 0))
    for row in rows:
        row[f"{row['measure']}_hours"] = row.pop("hours")
    return result(FIELDS, rows, makerspace_id, limit, definition=(
        "Service hours use terminal recorded duration; manual hours use the usage ledger; "
        "booked hours use reservations by machine type. Measures must never be added."
    ), limitations="Bookings bucket by start; unattributed manual history buckets by creation. Each measure keeps its top five machines/types over the whole window, plus Other partitioned by type.")


def _top_five_series(rows):
    totals = {}
    for row in rows:
        key = (row["makerspace_id"], row["measure"])
        identity = row["machine_type_id"] if row["measure"] == "booked" else row["machine_id"]
        ranks = totals.setdefault(key, {})
        ranks[identity] = ranks.get(identity, Decimal(0)) + row["hours"]
    keep = {key: set(sorted(ranks, key=lambda identity: (-ranks[identity], identity or 0))[:5]) for key, ranks in totals.items()}
    others, output = {}, []
    for row in rows:
        key = (row["makerspace_id"], row["measure"])
        identity = row["machine_type_id"] if row["measure"] == "booked" else row["machine_id"]
        if identity in keep[key]:
            output.append(row)
            continue
        other_key = (*key, row["period"], row["machine_type_id"])
        other = others.setdefault(other_key, {**row, "machine_id": None, "machine_name": "Other", "entries": 0, "hours": Decimal(0)})
        other["entries"] += row["entries"]
        other["hours"] += row["hours"]
    return [*output, *others.values()]


def build_machine_usage_members(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    groups = {}
    for space, scope in spaces(makerspace_id, ("machines",), actor, identities=True):
        for fact in usage_facts(space, scope, date_range, grain):
            # Null is an explicit unattributed bucket, never requester or logged_by.
            key = (fact["period"], fact["member_id"], fact["measure"], fact["machine_type_id"])
            target = groups.setdefault(key, {field: fact[field] for field in MEMBER_FIELDS[:-2]})
            target["entries"] = target.get("entries", 0) + 1
            target["hours"] = target.get("hours", Decimal(0)) + fact["hours"]
    rows = sorted(groups.values(), key=lambda r: (-r["hours"], r["member_id"] or 0, r["period"], r["measure"]))
    return result(MEMBER_FIELDS, rows, makerspace_id, limit, limitations="Null member_id means unattributed; no identity is inferred from contact fields or staff actors.")
