"""Superadmin platform overview (#183A): every space's totals, combined, beside the breakdown.

A deliberate, owner-decided exception to "aggregates never flatten cross-tenant data"
(docs/INVARIANTS.md): a platform total may ACCOMPANY, never replace, the per-space rows,
which are always in the same payload. Money is never summed across currencies.

Authority is checked by the view (active superadmin, browser session); this builder
holds no actor and reads no person-identifying field, so the Celery task can run it.
"""

from django.utils import timezone

from apps.makerspaces.servability import is_servable
from apps.operations.platform_dashboard import platform_spaces
from apps.operations.platform_overview_activity import BOOKINGS, EVENTS, MACHINES, MEMBERSHIP
from apps.operations.platform_overview_money import SWITCHES as MONEY_SWITCHES, money_section
from apps.operations.platform_overview_ops import OPERATIONS, module_matrix
from apps.operations.platform_overview_people import LENDING, PEOPLE

BLOCKS = (PEOPLE, LENDING, MACHINES, EVENTS, BOOKINGS, MEMBERSHIP, OPERATIONS)


def exclusion_reason(space):
    """Why a space is left out by default: archived, not serving (importing/aborted), or hidden
    from the central directory. The one toggle adds all three back (#183A)."""
    if space.archived_at is not None:
        return "archived"
    if not is_servable(space):
        return space.lifecycle_state
    if space.hidden_from_central_directory:
        return "directory_hidden"
    return None


def select_spaces(include_excluded):
    everything = list(platform_spaces().order_by("name", "pk"))
    excluded = [space for space in everything if exclusion_reason(space)]
    chosen = everything if include_excluded else [space for space in everything if not exclusion_reason(space)]
    return chosen, excluded


def _metric_payload(metric):
    return {"key": metric.key, "label": metric.label, "unit": metric.unit, "timing": metric.timing}


def _total(metric, values):
    total = sum(value for value in values if value is not None)
    return round(total, 1) if metric.unit == "hours" else total


def build_block(block, spaces, window, now):
    on = [space for space in spaces if block.gate(space)]
    base = {"key": block.key, "label": block.label, "switches": list(block.switches),
            "on_in": len(on), "off_in": len(spaces) - len(on)}
    if not on:
        return None, base
    data = block.collect([space.pk for space in on], window, now)
    on_ids = {space.pk for space in on}
    per_space = {}
    for space in spaces:
        if space.pk not in on_ids:
            per_space[space.pk] = None  # the module is off here: shown as "off", never as 0
            continue
        per_space[space.pk] = {metric.key: data.get(metric.key, {}).get(space.pk, 0)
                               for metric in block.metrics if metric.summable}
    totals = {metric.key: _total(metric, (row.get(metric.key) for row in per_space.values() if row))
              for metric in block.metrics if metric.summable}
    for key, derive in (block.derive or {}).items():
        rows, total = derive(per_space, totals, window)
        totals[key] = total
        for space_id, value in rows.items():
            per_space[space_id][key] = value
    platform = block.collect_platform(window, now) if block.collect_platform else {}
    return {**base,
            "metrics": [_metric_payload(metric) for metric in block.metrics],
            "totals": totals,
            "rows": [{"makerspace_id": space_id, "values": values} for space_id, values in per_space.items()],
            "platform_metrics": [{**_metric_payload(metric), "value": platform.get(metric.key, 0)}
                                 for metric in block.platform_metrics]}, None


def build_platform_overview(window, *, include_excluded=False, now=None):
    now = now or timezone.now()
    spaces, excluded = select_spaces(include_excluded)
    blocks, hidden = [], []
    for block in BLOCKS:
        built, off = build_block(block, spaces, window, now)
        if built is not None:
            blocks.append(built)
        else:
            hidden.append(off)
    money = money_section(spaces, window)
    if money is None:
        hidden.append({"key": "money", "label": "Money", "switches": list(MONEY_SWITCHES), "on_in": 0, "off_in": len(spaces)})
    return {
        "status": "ready", "computed_at": now,
        "window": {"preset": window.preset, "starts_at": window.start, "ends_at": window.end},
        "include_excluded": include_excluded,
        "excluded_count": len(excluded),
        "spaces": [{"id": space.pk, "name": space.name, "slug": space.slug,
                    "excluded_reason": exclusion_reason(space),
                    "directory_hidden": bool(space.hidden_from_central_directory)} for space in spaces],
        "blocks": blocks, "money": money, "hidden_blocks": hidden,
        "modules": module_matrix(spaces),
    }
