"""Public-stat page controls and area-owned visibility, through the L17 write gate.

The group is page on/off (the existing `public_stats_enabled`), the ordered sections, one
fixed period, up to four headline numbers and the TV mode. Every write goes through the
settings-authority layer. Page-wide controls use `public_site` (Space Manager only);
widget visibility uses its catalogue owner and that area's existing grants and locks.
Each changed key is audited with the authority under which it was written.
Defaults keep the page as it was before #170: machines, printing and lending, no headline
row, TV mode off.
"""

from django.utils.translation import gettext

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
from .public_stats_catalogue import METRICS, WIDGETS, read_visibility

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
        "visibility": read_visibility(makerspace),
        "sections": _keys(makerspace.public_stats_sections, SECTIONS),
        "period": period if period in PERIODS else DEFAULT_PERIOD,
        "headline": _keys(makerspace.public_stats_headline, METRICS, MAX_HEADLINE),
        "tv_mode_enabled": bool(makerspace.public_stats_tv_mode_enabled),
        "tv_refresh_seconds": min(max(refresh, TV_REFRESH_MIN), TV_REFRESH_MAX),
    }


def _stored(name, value):
    return ",".join(value) if name in LIST_FIELDS else value


from .public_stats_settings_writes import save_config  # noqa: E402 -- compatibility export


def choices():
    """What the settings panel offers; labels are server-owned so the page and panel agree."""
    return {
        "sections": [{"key": key, "label": gettext(label)} for key, label in SECTIONS.items()],
        "periods": [{"key": key, "label": gettext(label)} for key, label in PERIODS.items()],
        "metrics": [{"key": key, "section": section, "label": gettext(label)}
                    for key, (section, label, _kind) in METRICS.items()],
        "widgets": [{"key": widget.key, "section": widget.section, "owner_module": widget.owner_module,
                     "label": gettext(widget.label), "kind": widget.kind} for widget in WIDGETS.values()],
        "max_headline": MAX_HEADLINE,
        "tv_refresh_min": TV_REFRESH_MIN,
        "tv_refresh_max": TV_REFRESH_MAX,
    }
