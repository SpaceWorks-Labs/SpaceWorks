"""The 80 / 100 percent limit warnings (decision 328a): notify once per crossing, reset when usage drops.

``sweep_space`` compares every limited key of a space with the level stored in ``SpaceLimitThreshold``:
rising to 80 or 100 notifies the Space Managers and superadmins (``limit_notices.notify_threshold``) and stores the
level; falling back under 80, or the limit being removed, deletes the row so the next crossing notifies again.
A fall from 100 to the 80 band keeps the 80 row (no second 80 notice) and lets the next 100 notify.
Existing data is never touched; this only reads counters and writes the marker and inbox rows.
"""
import logging
from datetime import UTC, datetime

from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write

from .limit_notices import notify_threshold
from .limit_overview import overview_rows
from .models import SpaceLimitThreshold

logger = logging.getLogger(__name__)
LEVELS = {"ok": 0, "warning": 80, "limit": 100}


def sweep_space(space):
    """Returns ``{"notified": [(key, level)], "reset": [key]}``."""
    from .availability import plans_enabled
    from .limit_defaults import any_default

    if not (space.resource_limit_overrides or plans_enabled() or any_default() or
            SpaceLimitThreshold.objects.filter(makerspace=space).exists()):
        return {"notified": [], "reset": []}  # nothing can be limited: skip every counter
    period = datetime.now(UTC).strftime("%Y-%m")
    rows = {row["key"]: row for row in overview_rows(space, limited_only=True)}
    notified, reset = [], []
    with tenant_write(space.pk):  # markers and inbox rows are tenant writes: a gated space is skipped
        marks = {m.key: m for m in SpaceLimitThreshold.objects.select_for_update().filter(makerspace=space)}
        for key, mark in marks.items():
            row = rows.get(key)
            if row is None or LEVELS[row["level"]] == 0:
                mark.delete()
                reset.append(key)
        for key, row in rows.items():
            level = LEVELS[row["level"]]
            mark = marks.get(key)
            previous = mark.level if mark and key not in reset else 0
            if level > previous:
                SpaceLimitThreshold.objects.update_or_create(makerspace=space, key=key, defaults={"level": level})
                notify_threshold(space, key, row["label"], level, row["percent"] or 0, period)
                audit.record(None, "managed_hosting.limit_threshold_crossed", makerspace=space, target=space,
                             meta={"key": key, "level": level, "percent": int(row["percent"] or 0)})  # audit meta takes no floats
                notified.append((key, level))
            elif 0 < level < previous:
                SpaceLimitThreshold.objects.filter(makerspace=space, key=key).update(level=level)
    return {"notified": notified, "reset": reset}


def sweep_all():
    """Every active space; one failing space never stops the rest."""
    from apps.makerspaces.models import Makerspace

    totals = {"spaces": 0, "notified": 0, "reset": 0}
    for space in Makerspace.objects.all().iterator():
        try:
            result = sweep_space(space)
        except Exception:  # noqa: BLE001
            logger.warning("limit_threshold_sweep_failed", extra={"makerspace_id": space.pk}, exc_info=True)
            continue
        totals["spaces"] += 1
        totals["notified"] += len(result["notified"])
        totals["reset"] += len(result["reset"])
    return totals
