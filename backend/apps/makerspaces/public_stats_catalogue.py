"""Canonical public-stat visibility keys, owning settings area and public projection paths."""
from dataclasses import dataclass

from django.utils.translation import gettext_noop as _


METRICS = {
    "events.upcoming": ("events", _("Upcoming events"), "count"),
    "events.held": ("events", _("Events held"), "count"),
    "events.attendees": ("events", _("Event attendees"), "count"),
    "machines.hours": ("machines", _("Machine hours"), "hours"),
    "printing.hours": ("printing", _("Print hours"), "hours"),
    "printing.jobs": ("printing", _("Prints completed"), "count"),
    "lending.loans": ("lending", _("Loans"), "count"),
    "lending.library": ("lending", _("Tools in the library"), "count"),
    "community.active_members": ("community", _("Active members"), "count"),
    "community.new_members": ("community", _("New members"), "count"),
    "community.bookings": ("community", _("Bookings"), "count"),
    "community.checkins": ("community", _("Check-ins"), "count"),
}


@dataclass(frozen=True)
class Widget:
    key: str
    section: str
    owner_module: str
    label: str
    kind: str
    paths: tuple[tuple[str, ...], ...] = ()


_OWNERS = {"events": "events", "machines": "machines", "printing": "machines",
           "lending": "inventory", "community": "public_site"}
_METRIC_PATHS = {
    "events.upcoming": (("events", "upcoming_count"),),
    "events.held": (("events", "held"),),
    "events.attendees": (("events", "attendees"),),
    "lending.library": (("hardware", "library", "library_size"),),
    **{f"community.{name}": (("community", name),)
       for name in ("active_members", "new_members", "bookings", "checkins")},
}
WIDGETS = {
    key: Widget(key, section, "bookings" if key == "community.bookings" else _OWNERS[section],
                label, kind, _METRIC_PATHS.get(key, ()))
    for key, (section, label, kind) in METRICS.items()
}
for _widget in (
    Widget("events.upcoming_list", "events", "events", _("Upcoming event cards"), "list", (("events", "upcoming"),)),
    Widget("machines.hours_all_time", "machines", "machines", _("Machine hours all time"), "hours", (("machines", "usage_hours"),)),
    Widget("printing.hours_all_time", "printing", "machines", _("Print hours all time"), "hours", (("printing", "hours_all_time"),)),
    Widget("printing.hours_this_month", "printing", "machines", _("Print hours this month"), "hours", (("printing", "hours_this_month"),)),
    Widget("printing.grams_all_time", "printing", "machines", _("Filament used"), "weight", (("printing", "grams_all_time"),)),
    Widget("printing.completed_jobs", "printing", "machines", _("Completed print jobs all time"), "count",
           (("printing", "jobs", "completed"), ("printing", "jobs", "status_counts", "completed"))),
    Widget("printing.busiest_printer", "printing", "machines", _("Busiest printer"), "detail", (("printing", "busiest_printer"),)),
    Widget("printing.queue", "printing", "machines", _("Print queue and status summary"), "detail",
           (("printing", "jobs", "queue"), ("printing", "jobs", "status_counts"))),
    Widget("printing.by_brand", "printing", "machines", _("Filament by brand"), "list", (("printing", "by_brand"),)),
    Widget("printing.filament_trend", "printing", "machines", _("Filament trend"), "list", (("printing", "filament_trend"),)),
    Widget("printing.per_printer", "printing", "machines", _("Per-printer activity"), "list", (("printing", "per_printer"),)),
    Widget("lending.available", "lending", "inventory", _("Available tools now"), "count", (("hardware", "library", "available_count"),)),
    Widget("lending.currently_out", "lending", "inventory", _("Tools currently out"), "count", (("hardware", "library", "currently_out_count"),)),
    Widget("lending.most_popular", "lending", "inventory", _("Most popular tools"), "list", (("hardware", "most_popular"),)),
    Widget("lending.tools_out", "lending", "inventory", _("Tools out"), "list", (("hardware", "tools_out"),)),
    Widget("lending.recently_added", "lending", "inventory", _("Recently added tools"), "list", (("hardware", "recently_added"),)),
    Widget("lending.current_loans", "lending", "inventory", _("Current public loans"), "list", (("current_loans",),)),
):
    WIDGETS[_widget.key] = _widget


def visibility_setting_key(key):
    return f"public_stats.visibility.{key}"


SETTING_KEYS = tuple((widget.owner_module, visibility_setting_key(widget.key)) for widget in WIDGETS.values()
                     if widget.owner_module != "public_site")


def read_visibility(makerspace):
    config = getattr(makerspace, "public_stats_config", {})
    if not isinstance(config, dict):
        return dict.fromkeys(WIDGETS, False)
    raw = config.get("visibility", {})
    if not isinstance(raw, dict):
        return dict.fromkeys(WIDGETS, False)
    return {key: raw.get(key, True) if key not in raw or type(raw[key]) is bool else False for key in WIDGETS}


def source_available(makerspace, key):
    from django.http import Http404
    from .editions import public_surface_available
    from .guards import SurfaceOff
    from .platform import module_enabled

    section = WIDGETS[key].section
    if section == "community":
        module = {"community.active_members": "membership", "community.new_members": "membership",
                  "community.bookings": "bookings", "community.checkins": "presence"}[key]
        return public_surface_available(module) and module_enabled(makerspace, module)
    if section == "lending":
        from .public_site import require_public_catalogue
        try:
            require_public_catalogue(makerspace)
        except (Http404, SurfaceOff):
            return False
        if key in {"lending.loans", "lending.current_loans", "lending.most_popular"}:
            return public_surface_available("request_workflow") and module_enabled(makerspace, "request_workflow")
        return True
    surface = section
    required = ("machine_service", "printing") if section == "printing" else (surface,)
    return public_surface_available(surface) and all(module_enabled(makerspace, module) for module in required)
