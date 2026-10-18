"""Operational counts combine from their underlying numerators and sample sizes."""

from apps.operations.reports_common import limited
from apps.operations.reports_j_common import rate
from apps.operations.report_fields_j import DEVICE_SUM_FIELDS as SUM_FIELDS, ORGANIZATION_COUNTS as COUNTS


def combine_device_health(rows_by_space, *, limit):
    groups = {}
    for _, rows in rows_by_space:
        for row in rows:
            key = row["period"], row["device_id"]
            state = groups.setdefault(key, {"period": key[0], "device_id": key[1], **dict.fromkeys(SUM_FIELDS, 0)})
            for field in SUM_FIELDS:
                state[field] += row[field]
    for state in groups.values():
        state["uptime_percent"] = rate(state["online_seconds"], state["online_seconds"] + state["offline_seconds"])
        state["command_success_percent"] = rate(state["commands_acknowledged"], state["commands_acknowledged"] + state["commands_failed"])
    return limited([groups[key] for key in sorted(groups)], limit)


def combine_presence(rows_by_space, *, limit):
    groups = {}
    for _, rows in rows_by_space:
        for row in rows:
            state = groups.setdefault(row["period"], {"period": row["period"], "visits": 0, "declared_presence_seconds": 0, "_visitors": set()})
            state["visits"] += row["visits"]
            state["declared_presence_seconds"] += row["declared_presence_seconds"]
            state["_visitors"].update(row["_visitors"])
    for state in groups.values():
        state["unique_visitors"] = len(state.pop("_visitors"))
        state["average_declared_presence_seconds"] = state["declared_presence_seconds"] / state["visits"] if state["visits"] else None
    return limited([groups[key] for key in sorted(groups)], limit)


def combine_audit(rows_by_space, *, limit):
    groups = {}
    for _, rows in rows_by_space:
        for row in rows:
            key = row["period"], row["action"]
            state = groups.setdefault(key, {"period": key[0], "action": key[1], "count": 0})
            state["count"] += row["count"]
    return limited(sorted(groups.values(), key=lambda r: (-r["count"], r["period"], r["action"])), limit)


def combine_organization_membership(rows_by_space, *, limit):
    # The same global organization is projected at each owner-linked tenant. Its
    # cohort is identical in UTC and is counted once, never summed per owner link.
    groups = {}
    for _, rows in rows_by_space:
        for row in rows:
            key = row["period"], row["organization_id"]
            if key not in groups:
                groups[key] = {field: row[field] for field in ("period", "organization_id", *COUNTS)}
    for state in groups.values():
        state["redemption_percent"] = rate(state["redeemed"], state["invitations"])
    return limited([groups[key] for key in sorted(groups)], limit)
