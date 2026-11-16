"""More /control/ home panels (0.12.0): backups, limits near quota, the group map, internal records.

Counts, dates and space names only -- never a person. Each panel fails on its own: a broken
query shows "could not be read" in that card and leaves the rest of the home page working.
"""

import logging

from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from config.control_catalog import HIDDEN, SECTIONS

logger = logging.getLogger(__name__)


def _link(route, query=""):
    try:
        return reverse(route) + query
    except NoReverseMatch:  # a tombstoned app's page
        return None


def backup_status():
    """The newest whole-platform backup, the last backup run, the last drill and off-site copies."""
    try:
        from apps.backup.models import BackupArchive
        from apps.backup.models_drill import RestoreDrillReport
        from apps.backup.models_offsite import BackupDestination, BackupDestinationUpload
        from apps.backup.models_runs import BackupRun

        platform = (BackupArchive.objects.filter(scope=BackupArchive.Scope.DEPLOYMENT, status=BackupArchive.Status.AVAILABLE)
                    .order_by("-created_at").values_list("created_at", flat=True).first())
        run = BackupRun.objects.order_by("-started_at").values("status", "started_at", "finished_at").first()
        drill = RestoreDrillReport.objects.order_by("-started_at").values("outcome", "started_at").first()
        upload = BackupDestinationUpload.objects.order_by("-pk").values("state").first()
        return {
            "ok": True,
            "platform_at": platform,
            "run": run,
            "drill": drill,
            "destinations": BackupDestination.objects.filter(retired_at__isnull=True).count(),
            "upload_state": upload["state"] if upload else None,
            "link": _link("admin:backup_platformbackupsettings_console"),
        }
    except Exception:  # noqa: BLE001 - the home page never fails on one panel
        logger.warning("control_dashboard.backups_unavailable", exc_info=True)
        return {"ok": False}


def limits_near():
    """Spaces at 80 % or more of a limit or quota (only spaces with a limit set are visited)."""
    try:
        from config.control_limits import HOME_SPACES, limits_overview

        data = limits_overview(cap=HOME_SPACES)
        return {"ok": True, "rows": data["near"][:8], "more": max(len(data["near"]) - 8, 0),
                "capped": data["capped"], "link": _link("admin:managed_hosting_spacehostingtype_limits")}
    except Exception:  # noqa: BLE001
        logger.warning("control_dashboard.limits_unavailable", exc_info=True)
        return {"ok": False}


def group_map():
    """Each sidebar group with its icon, one-line description and a link to its first screen."""
    groups = []
    for section in SECTIONS:
        link = next((url for entry in section.entries if entry.route != "admin:index" and (url := _link(entry.route))),
                    None)
        if link is None:
            continue
        groups.append({"key": section.key, "title": section.title, "icon": section.icon,
                       "description": section.description, "link": link, "count": len(section.entries)})
    return groups


def internal_records():
    return [{"label": entry.title, "link": link} for entry in HIDDEN if (link := _link(entry.route))]


# The web superadmin console's platform pages, in the same groups (PUBLIC_APP_BASE_URL + path).
CONSOLE_PAGES = (
    (_("Platform dashboard"), "/admin/platform-dashboard"),
    (_("Spaces"), "/admin/platform-spaces"),
    (_("People & access"), "/admin/platform-access"),
    (_("Platform security"), "/admin/platform-security"),
    (_("Data & recovery"), "/admin/platform-data"),
    (_("Platform analytics"), "/admin/platform-analytics"),
    (_("Platform settings"), "/admin/platform"),
)


def console_links(base_url):
    base = (base_url or "").rstrip("/")
    if not base:
        return []
    return [{"label": label, "link": f"{base}{path}"} for label, path in CONSOLE_PAGES]
