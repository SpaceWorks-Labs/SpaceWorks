"""Remaining allowance per role (#234 addendum 3(a), #224: each role sees only what it manages).

The Space Manager (and the superadmin) see every limited row of the space; an area manager sees
only the rows of the areas whose action they hold. Rows come from ``effective_limits`` -- the
same counters enforcement reads -- and only LIMITED rows are returned, so with hosting off (or
no limits set) every role gets an empty list and nothing renders.
"""

from apps.accounts import rbac

from .limits_console import effective_limits
from .usage import level

A = rbac.Action
# area -> (limit keys, any of these actions opens it). A key may sit in two areas.
AREAS = {
    "inventory": (frozenset({"products", "assets", "storage", "upload_bytes", "storage_evidence_bytes",
                             "storage_public_images_bytes", "hardware_requests_monthly", "stock_transfers_monthly",
                             "stocktake_sessions_monthly", "shelf_checks_monthly"}), (A.EDIT_INVENTORY,)),
    "machines": (frozenset({"machines", "print", "machine_service_open", "machine_service_submit",
                            "machine_jobs_monthly", "machine_sessions_monthly"}),
                 (A.MANAGE_MACHINES, A.MANAGE_PRINTING)),
    "events": (frozenset({"events", "events_monthly", "guest_passes", "event_registrations_monthly",
                          "reimbursement_claims_monthly"}),
               (A.MANAGE_EVENTS,)),
    "bookings": (frozenset({"bookings", "bookings_monthly", "bookable_spaces"}), (A.MANAGE_BOOKINGS,)),
    "members": (frozenset({"members", "guest_passes", "member_units"}), (A.MANAGE_MEMBERS,)),
    # PE9 (open item A29): the shop has no counter of its own, but its product photos draw on the
    # space's storage and upload cap; the staff seat limit sits with the people who add staff.
    "shop": (frozenset({"storage", "upload_bytes", "shop_orders_monthly", "shop_products",
                        "storage_public_images_bytes"}), (A.MANAGE_SHOP,)),
    "staff": (frozenset({"staff", "api_clients", "membership_plans", "organizations_linked", "kiosk_stations", "paired_displays",
                         "api_requests_per_minute", "analytics_connections", "report_exports_monthly",
                         "webhook_endpoints", "public_page_assets", "scheduled_reports", "anthias_players"}),
              (A.MANAGE_MAKERSPACE,)),
    # Decision 284 addendum: the resources whose own action opens a narrower area.
    "qr": (frozenset({"boxes"}), (A.MANAGE_QR,)),
    "devices": (frozenset({"devices", "adapter_bridges", "adapter_watch_streams", "adapter_snapshots", "adapter_artifacts", "adapter_media_bytes",
                         "adapter_telemetry_points"}), (A.MANAGE_DEVICES,)),
    "donations": (frozenset({"donation_campaigns"}), (A.MANAGE_DONATIONS,)),
}
AREA_NAMES = tuple(AREAS)


def visible_areas(actor, makerspace):
    """``(areas, sees_everything)`` for this actor in this space."""
    if rbac.is_space_manager_identity(actor, makerspace.pk):
        return AREA_NAMES, True
    actions = rbac.effective_actions(actor, makerspace.pk)
    return tuple(name for name, (_keys, needs) in AREAS.items() if actions & set(needs)), False


def _key_of(row):
    return row["key"]


def _quota_rows(makerspace, keys, taken):
    """Superadmin-set quota rows (monthly events/bookings and every decision-284 key), limited ones only."""
    from .space_quotas import usage_rows
    for row in usage_rows(makerspace):
        limit, used = row["limit"], row["used"]
        if limit is None or row["key"] in taken or (keys is not None and row["key"] not in keys):
            continue
        yield {"key": row["key"], "label": row["label"], "unit": row["unit"], "limit": limit, "used": used,
               "remaining": None if used is None else max(0, limit - used), "percent": row["percent"],
               "level": row["level"], "areas": [name for name, (k, _a) in AREAS.items() if row["key"] in k]}


def allowance_rows(actor, makerspace, area=None):
    """The actor's limited rows, each with ``remaining``, ``percent`` and ``level`` (80 % / 100 %)."""
    areas, everything = visible_areas(actor, makerspace)
    if area is not None:
        areas = tuple(name for name in areas if name == area)
        everything = False
    keys = None if everything else frozenset().union(*(AREAS[name][0] for name in areas))
    rows = []
    for row in effective_limits(makerspace, keys, limited_only=True):
        limit, used = row["effective"], row["used"]
        percent = None
        if used is not None:
            percent = 100.0 if limit == 0 else round(used * 100 / limit, 1)
        rows.append({
            "key": row["key"], "label": row["label"], "unit": row["unit"], "limit": limit, "used": used,
            "remaining": None if used is None else max(0, limit - used), "percent": percent,
            "level": level(percent), "areas": [name for name, (k, _a) in AREAS.items() if row["key"] in k],
        })
    rows.extend(_quota_rows(makerspace, keys, {row["key"] for row in rows}))
    rows.sort(key=_key_of)
    return {"makerspace_id": makerspace.pk, "areas": list(areas), "rows": rows}
