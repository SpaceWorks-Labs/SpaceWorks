"""Every other countable per-space resource (decision 284 addendum): superadmin-set, default NONE, any space.

One registry (``SPECS``), one counter table (``extra_quota_counters``), one check. A limit lives in
``Makerspace.resource_limit_overrides`` (absent / null / -1 = no limit) and refuses only the START of
something new with the typed 409 ``<key>_quota_reached`` (``ExtraQuotaReached``). It never blocks reading,
exporting data, settling or refunding money, returns of issued items, or member privacy requests.

Units: ``count`` (rows now or this UTC month), ``bytes`` (managed storage), ``per_minute`` (a request rate,
``api_requests_per_minute``: it can only LOWER the API-client tier rate, see ``apiclients/throttling.py``).
"""
from django.utils.translation import gettext
from rest_framework.exceptions import APIException

from apps.makerspaces.limits_core import EXTRA_QUOTA_LIMIT_KEYS

from .extra_quota_counters import COUNTERS
from .space_quotas import SpaceQuotaReached, quota_limit

# key -> (unit, label). The console area of each key is in ``makerspaces/limit_registry.AREA_OF``.
SPECS = {
    "event_registrations_monthly": ("count", "event registrations and tickets this month"),
    "shop_orders_monthly": ("count", "shop orders this month"),
    "shop_products": ("count", "shop products"),
    "membership_plans": ("count", "membership plans"),
    "donation_campaigns": ("count", "active donation campaigns and funds"),
    "bookable_spaces": ("count", "bookable spaces"),
    "boxes": ("count", "QR boxes"),
    "organizations_linked": ("count", "linked organizations"),
    "api_requests_per_minute": ("per_minute", "API requests per minute for each API client"),
    "analytics_connections": ("count", "analytics connections (Metabase or Grafana)"),
    "report_exports_monthly": ("count", "report exports this month"),
    "kiosk_stations": ("count", "kiosk stations"),
    "devices": ("count", "enrolled devices"),
    "machine_jobs_monthly": ("count", "machine jobs requested this month"),
    "machine_sessions_monthly": ("count", "machine sessions started this month"),
    "storage_evidence_bytes": ("bytes", "storage used by evidence photos"),
    "storage_public_images_bytes": ("bytes", "storage used by public images and other non-evidence files"),
    "webhook_endpoints": ("count", "outbound webhook endpoints"),
    "member_cards_issued_monthly": ("count", "member cards issued this month"),
    "wallet_passes": ("count", "member and event wallet passes"),
    "staff_cards_issued_monthly": ("count", "staff ID cards issued this month"),
    "member_units": ("count", "member units (districts, chapters, branches)"),
    "series_invites": ("count", "series invite-list entries"),
    "checkin_lists": ("count", "check-in lists on one event"),
    "event_badge_prints_monthly": ("count", "event badges printed this month"),
    "hackathon_stages": ("count", "submission stages on one hackathon"),
    "saved_views": ("count", "saved views per person on one event list"),
    "collection_sheet_rows_monthly": ("count", "collection sheet rows this month"),
    "paired_displays": ("count", "paired space display screens"),
    "adapter_bridges": ("count", "enrolled device adapters (bridges)"),
    "adapter_watch_streams": ("count", "camera watch sessions open at once"),
    "adapter_snapshots": ("count", "camera snapshots requested this month"),
    "adapter_artifacts": ("count", "adapter timelapses, previews and bundles kept"),
    "photo_cutout_jobs_monthly": ("count", "card photo background-removal jobs this month"),
    "card_templates": ("count", "saved card and certificate templates"),
    # 0.12.0 (decision 328a)
    "hardware_requests_monthly": ("count", "hardware requests submitted this month"),
    "stock_transfers_monthly": ("count", "stock transfers made this month"),
    "stocktake_sessions_monthly": ("count", "stocktake sessions started this month"),
    "shelf_checks_monthly": ("count", "shelf checks saved this month"),
    "reimbursement_claims_monthly": ("count", "event reimbursement claims started this month"),
    "public_page_assets": ("count", "images on the public space page"),
    "scheduled_reports": ("count", "active scheduled reports"),
    "adapter_media_bytes": ("bytes", "storage used by device adapter timelapses, previews and bundles"),
    "adapter_telemetry_points": ("count", "device telemetry samples kept"),
    "anthias_players": ("count", "registered Anthias display players"),
}
assert set(SPECS) == EXTRA_QUOTA_LIMIT_KEYS
HEAVY_COUNTERS = frozenset({"adapter_telemetry_points"})


class ExtraQuotaReached(SpaceQuotaReached):
    def __init__(self, key, limit):
        message = gettext("This space has reached its allowance of %(what)s (%(limit)s). "
                          "Ask the platform operator to raise it.") % {"what": gettext(SPECS[key][1]), "limit": limit}
        self.code = f"{key}_quota_reached"
        APIException.__init__(self, {"detail": message, "code": self.code, "limit": limit})


def extra_used(makerspace, key):
    counter = COUNTERS.get(key)
    return None if counter is None else counter(makerspace)


def check_extra_quota(makerspace, key, *, adding=1):
    """Raise the typed 409 when ``adding`` more of ``key`` would pass the limit; a no-op while unlimited.

    Callers hold the row lock of what they create (event, space, order) or run inside the creating
    transaction, so concurrent creators are serialised the same way as ``limits.check_quota``.
    """
    if makerspace is None or not adding:
        return
    limit = quota_limit(makerspace, key)
    if limit is None:
        return
    if extra_used(makerspace, key) + adding > limit:
        raise ExtraQuotaReached(key, limit)


def check_extra_quota_locked(makerspace, key, *, adding=1):
    """``check_extra_quota`` for a creator that holds no other lock (L-M2): it locks the space row first,
    so two concurrent creators are counted one after the other and cannot both pass the last free slot.

    Must run inside the creating transaction. While the key is unlimited it neither locks nor counts.
    """
    if makerspace is None or not adding or quota_limit(makerspace, key) is None:
        return
    from apps.makerspaces.models import Makerspace

    Makerspace.objects.select_for_update().only("pk").get(pk=makerspace.pk)
    check_extra_quota(makerspace, key, adding=adding)


def check_scoped_quota(makerspace, key, used, *, adding=1):
    """Like ``check_extra_quota`` for a limit that applies per scope (one event, one person and list).

    The caller counts ``used`` inside its own locked scope; the usage page shows the busiest scope.
    """
    limit = None if makerspace is None else quota_limit(makerspace, key)
    if limit is not None and used + adding > limit:
        raise ExtraQuotaReached(key, limit)


def extra_quota_allows(makerspace, key, *, adding=1):
    """Like ``check_extra_quota`` but answers True/False, for a seam that cannot return a 409 (telemetry ingest)."""
    try:
        check_extra_quota(makerspace, key, adding=adding)
    except SpaceQuotaReached:
        return False
    return True


def check_storage_class(makerspace, key, size_bytes):
    """Refuse an upload that would push one storage class past its own byte limit (finalize time)."""
    check_extra_quota(makerspace, key, adding=int(size_bytes or 0))


def api_rate_limit(makerspace):
    """The space's own API-client rate (requests per minute) or None; it may only lower the tier rate."""
    return None if makerspace is None else quota_limit(makerspace, "api_requests_per_minute")


def usage_rows(makerspace, keys=None, *, limited_only=False):
    """Read-only rows for the superadmin console, the Space Manager page and area managers."""
    from apps.makerspaces.limit_registry import area_of

    from .usage import level
    rows = []
    for key in sorted(SPECS):
        if keys is not None and key not in keys:
            continue
        limit = quota_limit(makerspace, key)
        if limited_only and limit is None:
            continue
        try:
            # A counter over a huge table (telemetry samples) is only read once a limit makes it matter.
            used = extra_used(makerspace, key) if limit is not None or (not limited_only and key not in HEAVY_COUNTERS) else None
        except Exception:  # a counting failure must not break the page
            used = None
        percent = round(used * 100 / limit, 1) if limit and used is not None else (100.0 if limit == 0 else None)
        rows.append({"key": key, "label": SPECS[key][1], "unit": SPECS[key][0], "area": area_of(key),
                     "limit": limit, "used": used, "percent": percent, "level": level(percent)})
    return rows
