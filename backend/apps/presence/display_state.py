"""What a paired display receives: the logged-out public view of its space, for the panels it was given."""
from django.utils import timezone

from apps.makerspaces.platform import module_enabled
from .display_pairing import touch
from .display_panels_extra import inventory_highlights, sponsors_wall
from .here_now import here_now
from .display_config import apply_privacy
from .models_display import (
    PANEL_ANNOUNCEMENT, PANEL_CALENDAR, PANEL_HERE_NOW, PANEL_INVENTORY, PANEL_MACHINES, PANEL_OPENING_HOURS,
    PANEL_PUBLIC_STATS, PANEL_SPONSORS,
)
from .public_feed import calendar_events, machines_now


def waiting_state(row):
    return {"state": "unclaimed", "code": row.pairing_code, "code_expires_at": row.code_expires_at.isoformat()}


def paired_state(row, now=None):
    now = now or timezone.now()
    space = row.makerspace
    touch(row, now)
    panels = list(row.panels)
    payload = {
        "state": "paired",
        "generated_at": now.isoformat(),
        "space": {"name": space.name, "slug": space.slug, "timezone": space.timezone,
                  "theme": space.theme_config if isinstance(space.theme_config, dict) else {}},
        "config": {"name": row.name, "panels": panels, "rotation_seconds": row.rotation_seconds,
                   "version": row.config_version, "layout": row.layout, "theme": row.theme,
                   "privacy": row.privacy, "refresh_seconds": row.refresh_seconds,
                   "slide_seconds": row.slide_seconds or {}},
        "here_now": None, "calendar": None, "machines": None, "announcement": None,
        "public_stats": None, "opening_hours": None, "inventory_highlights": None, "sponsors": None,
    }
    if PANEL_HERE_NOW in panels and module_enabled(space, "presence"):
        payload["here_now"] = apply_privacy(here_now(space), row.privacy)  # anonymous audience, never a viewer
    if PANEL_CALENDAR in panels:
        payload["calendar"] = calendar_events(space, now=now)
    if PANEL_MACHINES in panels:
        payload["machines"] = machines_now(space)
    if PANEL_ANNOUNCEMENT in panels and row.announcement:
        payload["announcement"] = row.announcement
    if PANEL_PUBLIC_STATS in panels:
        payload["public_stats"] = public_stats_panel(space)
    if PANEL_OPENING_HOURS in panels and space.opening_hours:
        payload["opening_hours"] = space.opening_hours
    if PANEL_INVENTORY in panels:
        payload["inventory_highlights"] = inventory_highlights(space)
    if PANEL_SPONSORS in panels:
        payload["sponsors"] = sponsors_wall(space)
    return payload


def public_stats_panel(space):
    """Big-number tiles: only what the public stats page itself would show (switch, visibility, small-number rule)."""
    from apps.inventory.public_stats import build_public_stats
    from apps.makerspaces.public_stats_settings import read_config
    if not read_config(space)["enabled"]:
        return None
    stats = build_public_stats(space)
    rows = stats["headline"] or stats["metrics"]
    return {"period": stats["period"]["label"], "metrics": [
        {"key": m["key"], "label": m["label"], "value": m.get("value"), "kind": m["kind"], "suppressed": bool(m.get("suppressed"))} for m in rows[:8]]}


def state_for(row):
    if row.makerspace_id is None:
        return waiting_state(row)
    from .display_pairing import require_display
    require_display(row.makerspace)
    return paired_state(row)
