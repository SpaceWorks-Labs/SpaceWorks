"""The /control/ home dashboard (#188): key totals, what needs attention, quick links.

Read-only and superadmin-only (the index sits behind the same /control/ gates as every
other page). It never computes the heavy platform overview (#183A) inside the request: it
shows the cached overview when one exists and otherwise queues the one background
computation the web console would, exactly through ``platform_overview_cache``. Every
number is a count; no person is named.
"""

import logging

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from config.control_attention import attention_items

logger = logging.getLogger(__name__)
OVERVIEW_BLOCKS = ("people", "lending", "machines", "events", "bookings", "membership")


def _link(route, query=""):
    try:
        return reverse(route) + query
    except NoReverseMatch:  # a tombstoned app's page
        return None


def space_totals():
    from apps.accounts.models import User
    from apps.makerspaces.models import Makerspace
    from apps.organizations.models import Organization
    from apps.space_controls.models import SpaceControlState

    spaces = Makerspace.objects.all()
    controls = SpaceControlState.objects.all()
    return [
        {"label": "Spaces", "value": spaces.filter(archived_at__isnull=True).count(),
         "link": _link("admin:makerspaces_makerspace_changelist")},
        {"label": "Paused", "value": controls.filter(suspended_at__isnull=False).count(),
         "link": _link("admin:space_controls_spacecontrolstate_changelist")},
        {"label": "Read-only", "value": controls.filter(read_only_at__isnull=False).count(),
         "link": _link("admin:space_controls_spacecontrolstate_changelist")},
        {"label": "Archived", "value": spaces.filter(archived_at__isnull=False).count(),
         "link": _link("admin:makerspaces_makerspace_changelist")},
        {"label": "Accounts", "value": User.objects.filter(is_tenant_dump_stub=False, is_walk_in=False).count(),
         "link": _link("admin:accounts_user_changelist")},
        {"label": "Organizations", "value": Organization.objects.count(),
         "link": _link("admin:organizations_organization_changelist")},
    ]


def overview_totals():
    """This month's platform totals from the cached overview, or a status to show instead."""
    from apps.operations.platform_overview_cache import cache_key, read_or_schedule
    from apps.operations.platform_overview_window import resolve_window
    from django.core.cache import cache

    window = resolve_window("this_month")
    try:
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            # No broker: "scheduling" would compute inline, inside this page view.
            data = cache.get(cache_key(window, False)) or {"status": "not_computed"}
        else:
            data = read_or_schedule(window, False)
    except Exception:  # noqa: BLE001 - the home page never fails on the overview
        logger.warning("control_dashboard.overview_unavailable", exc_info=True)
        return {"status": "failed", "blocks": []}
    if data.get("status") != "ready":
        return {"status": data.get("status", "computing"), "blocks": []}
    blocks = []
    for block in data.get("blocks", []):
        if block.get("key") not in OVERVIEW_BLOCKS:
            continue
        figures = [{"label": metric["label"], "value": block["totals"].get(metric["key"])}
                   for metric in block.get("metrics", []) if metric["key"] in block.get("totals", {})][:4]
        blocks.append({"label": block["label"], "figures": figures,
                       "off_in": block.get("off_in", 0)})
    return {"status": "ready", "computed_at": data.get("computed_at"), "blocks": blocks}


def quick_links():
    rows = [
        ("Makerspaces", "admin:makerspaces_makerspace_changelist"),
        ("Accounts", "admin:accounts_user_changelist"),
        ("Audit log", "admin:audit_auditlog_changelist"),
        ("Backup console", "admin:backup_platformbackupsettings_console"),
        ("Backup keys, drills and notices", "admin:backup_backupkeyfingerprint_keys"),
        ("IP rules", "admin:accounts_ipaccessrule_changelist"),
        ("Email log", "admin:integrations_emaillog_changelist"),
        ("Scheduled task runs", "admin:operations_periodictaskrun_changelist"),
    ]
    links = [{"label": label, "link": link} for label, route in rows if (link := _link(route))]
    console = (getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")
    if console:
        links.append({"label": "Web superadmin console: platform overview", "link": f"{console}/admin/platform-dashboard",
                      "external": True})
    return links


def dashboard_callback(request, context):
    context.update({
        "control_home": True,
        "control_space_totals": space_totals(),
        "control_overview": overview_totals(),
        "control_attention": attention_items(timezone.now()),
        "control_links": quick_links(),
        "control_server_only": not getattr(settings, "CONTROL_PLANE_PROXY", False),
    })
    return context

