"""Public makerspace stats assembled only from canonical models (#170).

The Space Manager's Settings › Public stats group decides which sections show and in what
order, the one fixed period, the headline numbers and the TV mode. Each section is also
gated by its module (and the edition's public surface): a module that is off hides its
section and keeps its data. The legacy keys (`machines`, `printing`, `hardware`,
`current_loans`) keep their shapes and are `None` while their section is hidden.
"""

from apps.inventory.public_stats_activity import lending_loans, machine_hours, printing_figures
from apps.inventory.public_stats_community import community_metrics, community_section
from apps.inventory.public_stats_events import events_metrics, events_section
from apps.inventory.public_stats_hardware import (
    current_loans as _current_loans,
    hardware_stats as _hardware_stats,
)
from apps.inventory.public_stats_period import period_window, suppressed
from apps.inventory.public_stats_projection import apply_visibility
from apps.makerspaces.editions import public_surface_available
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.public_stats_settings import METRICS, read_config
from apps.makerspaces.public_stats_catalogue import source_available
from apps.machines.public_printer_stats import build_public_printer_stats
from apps.machines.public_stats import build_public_machine_stats

LEGACY_KEYS = ("machines", "printing", "hardware", "current_loans", "events", "community")


def _machines(makerspace, window):
    if not public_surface_available("machines"):
        return None
    stats = build_public_machine_stats(makerspace)
    if stats is None:
        return None
    return {"machines": stats}, {"machines.hours": machine_hours(makerspace, window)}


def _printing(makerspace, window):
    stats = _printing_stats(makerspace)
    if stats is None:
        return None
    figures = printing_figures(makerspace, window)
    return {"printing": stats}, {"printing.hours": figures["hours"], "printing.jobs": figures["jobs"]}


def _lending(makerspace, window):
    if not source_available(makerspace, "lending.library"):
        return None
    loans = source_available(makerspace, "lending.loans")
    hardware = _hardware_stats(makerspace, include_loan_history=loans)
    metrics = {"lending.loans": lending_loans(makerspace, window)} if loans else {}
    metrics["lending.library"] = suppressed(hardware["library"]["library_size"])
    return {"hardware": hardware, "current_loans": _current_loans(makerspace) if loans else []}, metrics


def _events(makerspace, window):
    section = events_section(makerspace, window)
    return None if section is None else ({"events": section}, events_metrics(section))


def _community(makerspace, window):
    section = community_section(makerspace, window)
    return None if section is None else ({"community": section}, community_metrics(section))


SECTION_BUILDERS = {
    "events": _events, "machines": _machines, "printing": _printing,
    "lending": _lending, "community": _community,
}


def _metric(key, value):
    section, label, kind = METRICS[key]
    row = {"key": key, "section": section, "label": label, "kind": kind}
    return {**row, **value} if kind == "count" else {**row, "value": value, "suppressed": False}


def build_public_stats(makerspace, *, now=None) -> dict:
    config = read_config(makerspace)
    window = period_window(makerspace, config["period"], now)
    payload = dict.fromkeys(LEGACY_KEYS)
    shown, metrics = [], {}
    for key in config["sections"]:
        built = SECTION_BUILDERS[key](makerspace, window)
        if built is None:
            continue
        data, section_metrics = built
        payload.update(data)
        metrics.update(section_metrics)
        shown.append(key)
    rows = [_metric(key, value) for key, value in metrics.items()]
    by_key = {row["key"]: row for row in rows}
    return apply_visibility(makerspace, {
        **payload,
        "sections": shown,
        "period": window.payload(),
        "headline": [by_key[key] for key in config["headline"] if key in by_key],
        "metrics": rows,
        "tv": {"enabled": config["tv_mode_enabled"], "refresh_seconds": config["tv_refresh_seconds"]},
    }, config)


def _printing_stats(makerspace):
    if not (public_surface_available("machine_service") and module_enabled(makerspace, "machine_service")):
        return None
    return build_public_printer_stats(makerspace)
