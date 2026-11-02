"""Settings › Public stats (#170): one per-space settings group, Space Manager only.

The group is page on/off (the existing `public_stats_enabled`), the ordered sections, one
fixed period, up to four headline numbers and the TV mode. Every write goes through the
settings-authority layer (`assert_setting_write`, module `public_site`): `public_site` has
no module manager, so only the Space Manager and the superadmin (#115) may change it, and
each changed key is audited as `settings.changed` with the authority it was made under.
Defaults keep the page as it was before #170: machines, printing and lending, no headline
row, TV mode off.
"""

from django.db import transaction

MODULE = "public_site"
SECTIONS = {
    "events": "Events",
    "machines": "Machines",
    "printing": "Printing",
    "lending": "Lending & inventory",
    "community": "Community",
}
DEFAULT_SECTIONS = ("machines", "printing", "lending")
PERIODS = {"month": "This month", "year": "This year", "all": "All time", "fy": "This financial year"}
DEFAULT_PERIOD = "month"
# metric key -> (section, label, kind). `count` values pass the small-number suppression.
METRICS = {
    "events.upcoming": ("events", "Upcoming events", "count"),
    "events.held": ("events", "Events held", "count"),
    "events.attendees": ("events", "Event attendees", "count"),
    "machines.hours": ("machines", "Machine hours", "hours"),
    "printing.hours": ("printing", "Print hours", "hours"),
    "printing.jobs": ("printing", "Prints completed", "count"),
    "lending.loans": ("lending", "Loans", "count"),
    "lending.library": ("lending", "Tools in the library", "count"),
    "community.active_members": ("community", "Active members", "count"),
    "community.new_members": ("community", "New members", "count"),
    "community.bookings": ("community", "Bookings", "count"),
    "community.checkins": ("community", "Check-ins", "count"),
}
MAX_HEADLINE = 4
TV_REFRESH_DEFAULT, TV_REFRESH_MIN, TV_REFRESH_MAX = 60, 30, 3600
# Setting name -> Makerspace column. The setting key is `public_stats.<name>`.
FIELDS = {
    "enabled": "public_stats_enabled",
    "sections": "public_stats_sections",
    "period": "public_stats_period",
    "headline": "public_stats_headline",
    "tv_mode_enabled": "public_stats_tv_mode_enabled",
    "tv_refresh_seconds": "public_stats_tv_refresh_seconds",
}
LIST_FIELDS = ("sections", "headline")


def setting_key(name):
    return f"public_stats.{name}"


def _keys(raw, allowed, limit=None):
    keys = [key for key in dict.fromkeys(part.strip() for part in str(raw or "").split(",")) if key in allowed]
    return keys[:limit] if limit else keys


def read_config(makerspace):
    """The normalised group: unknown or stale keys are dropped and the refresh clamped."""
    refresh = makerspace.public_stats_tv_refresh_seconds or TV_REFRESH_DEFAULT
    period = makerspace.public_stats_period
    return {
        "enabled": bool(makerspace.public_stats_enabled),
        "sections": _keys(makerspace.public_stats_sections, SECTIONS),
        "period": period if period in PERIODS else DEFAULT_PERIOD,
        "headline": _keys(makerspace.public_stats_headline, METRICS, MAX_HEADLINE),
        "tv_mode_enabled": bool(makerspace.public_stats_tv_mode_enabled),
        "tv_refresh_seconds": min(max(refresh, TV_REFRESH_MIN), TV_REFRESH_MAX),
    }


def _stored(name, value):
    return ",".join(value) if name in LIST_FIELDS else value


def save_config(actor, makerspace, values):
    """Write the changed settings, each through the authority layer and audited."""
    from apps.inventory.public_stats_cache import invalidate
    from apps.tenant_migration.gate_runtime import tenant_write

    from .models import Makerspace
    from .settings_authority import assert_setting_write, record_change

    # Every submitted key is checked, changed or not: a refused actor never gets a 200.
    decisions = {name: assert_setting_write(actor, makerspace, MODULE, setting_key(name))
                 for name in FIELDS if name in values}
    with tenant_write(makerspace.pk), transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        before = read_config(locked)
        changed = [name for name in decisions if values[name] != before[name]]
        if not changed:
            return before
        for name in changed:
            setattr(locked, FIELDS[name], _stored(name, values[name]))
        locked.save(update_fields=[*(FIELDS[name] for name in changed), "updated_at"])
        for name in changed:
            record_change(actor, locked, MODULE, setting_key(name), before[name], values[name], decisions[name])
        transaction.on_commit(lambda: invalidate(locked.pk))
    return read_config(locked)


def choices():
    """What the settings panel offers; labels are server-owned so the page and panel agree."""
    return {
        "sections": [{"key": key, "label": label} for key, label in SECTIONS.items()],
        "periods": [{"key": key, "label": label} for key, label in PERIODS.items()],
        "metrics": [{"key": key, "section": section, "label": label}
                    for key, (section, label, _kind) in METRICS.items()],
        "max_headline": MAX_HEADLINE,
        "tv_refresh_min": TV_REFRESH_MIN,
        "tv_refresh_max": TV_REFRESH_MAX,
    }
