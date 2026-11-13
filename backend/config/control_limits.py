"""Per-space limits for /control/ (decisions 281/284): which spaces have a limit set and how close they are.

Read-only. Reads the same rows the web console's limits table reads
(``apps.managed_hosting.limits_console.limit_rows``), so the numbers never disagree with
enforcement. Only spaces with something set are visited -- every limit defaults to none --
and the walk is capped so the page and the home dashboard stay cheap. A space whose counters
fail is skipped and counted, never allowed to break the page.
"""

import logging

logger = logging.getLogger(__name__)
PAGE_SPACES = 200
HOME_SPACES = 25


def _spaces(cap):
    from apps.makerspaces.models import Makerspace
    from apps.managed_hosting.models import SpacePlanAssignment

    ids = set(Makerspace.objects.exclude(resource_limit_overrides={})
              .exclude(resource_limit_overrides__isnull=True).values_list("id", flat=True)[:cap])
    ids |= set(SpacePlanAssignment.objects.values_list("makerspace_id", flat=True)[:cap])
    return list(Makerspace.objects.filter(id__in=ids).order_by("name")[:cap]), len(ids) > cap


def _percent(used, limit):
    if not isinstance(used, (int, float)) or not isinstance(limit, (int, float)):
        return None
    if limit == 0:
        return 100.0
    return round(used * 100 / limit, 1)


def _row(label, used, limit, unit, source, percent=None):
    from apps.managed_hosting.usage import level

    percent = percent if percent is not None else _percent(used, limit)
    return {"label": str(label), "used": used, "limit": limit, "unit": unit, "source": source,
            "percent": percent, "level": level(percent), "bar": min(percent or 0, 100)}


def space_rows(makerspace):
    """Every limit or quota set on one space, with its use this period."""
    from apps.managed_hosting.limits_console import limit_rows

    data = limit_rows(makerspace, limited_only=True)
    rows = [_row(r["label"], r["used"], r["effective"], r["unit"], r["source"])
            for r in data["rows"] if r["effective"] is not None]
    for source, extra in (("platform", data["platform_rows"]), ("quota", data["quota_rows"])):
        rows.extend(_row(r["label"], r["used"], r["limit"], r["unit"], source, r.get("percent"))
                    for r in extra if r.get("limit") is not None)
    return rows


def limits_overview(cap=PAGE_SPACES):
    from apps.managed_hosting.usage import WARNING_AT

    spaces, near, failed = [], [], 0
    visited, capped = _spaces(cap)
    for makerspace in visited:
        try:
            rows = space_rows(makerspace)
        except Exception:  # noqa: BLE001 - one space's counters never break the page
            logger.warning("control_limits.space_failed", extra={"makerspace_id": makerspace.pk}, exc_info=True)
            failed += 1
            continue
        if not rows:
            continue
        spaces.append({"space": makerspace, "rows": rows})
        near.extend({"space": makerspace, **row} for row in rows
                    if row["percent"] is not None and row["percent"] >= WARNING_AT)
    near.sort(key=lambda row: -row["percent"])
    return {"spaces": spaces, "near": near, "failed": failed, "capped": capped, "warning_at": WARNING_AT}
