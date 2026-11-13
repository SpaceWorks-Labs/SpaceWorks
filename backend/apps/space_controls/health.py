"""The per-space health card (#185 item 7): lifecycle state, usage against the existing
fair-use limits, last activity, backups and drills, security blocks, open issues and
modules. Counts only, no member names and no billing; the managers list carries account
names/emails, masked for a superadmin without a PII window on the space (#114: staff too).

Every space is listed, archived and paused included: this is the superadmin's recovery
surface. Each field reads the same source its own screen does (``usage_snapshot``, the
backup status line, the restore drill report, the tenant problem checks).
"""

from django.db.models import Max
from django.utils import timezone

from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable

from .models import SpaceControlState
from .notifications import manager_rows
from .services_schedule import is_archived


def state_label(space, control):
    if space.lifecycle_state == Makerspace.LifecycleState.SUSPENDED:
        return "suspended"
    if space.lifecycle_state != Makerspace.LifecycleState.ACTIVE:
        return space.lifecycle_state
    if control is not None and control.has_schedule:
        return "scheduled"
    if is_archived(space):
        return "archived"
    if control is not None and control.read_only_at is not None:
        return "read_only"
    return "active"


def has_state(card_data, wanted):
    """The state filter: the headline state, or a condition it outranks (a read-only space
    that also has a schedule is still read-only; an archived one with a purge due is archived)."""
    flags = {"read_only": card_data.get("read_only"), "archived": card_data.get("archived_at"),
             "scheduled": card_data.get("schedule"), "suspended": card_data.get("suspended")}
    return card_data["state"] == wanted or bool(flags.get(wanted))


def _who(user):
    return (user.display_name or user.username) if user is not None else None


def _usage(space):
    from apps.makerspaces.usage_snapshot import usage_snapshot

    snapshot = usage_snapshot(space)
    for row in snapshot["resources"]:
        used, limit = row["used"], row["limit"]
        row["percent"] = round(used * 100 / limit, 1) if used is not None and limit else None
    peaks = [row["percent"] for row in snapshot["resources"] if row["percent"] is not None]
    return {"managed": snapshot["managed"], "resources": snapshot["resources"]}, (max(peaks) if peaks else None)


def _backups(space):
    from apps.backup.models_drill import RestoreDrillReport
    from apps.backup.views_backup_status import last_backed_up_at

    drill = RestoreDrillReport.objects.filter(makerspace_id_snapshot=space.pk).order_by("-started_at").first()
    return {
        "last_backed_up_at": last_backed_up_at(space),
        "last_drill": {"outcome": drill.outcome, "finished_at": drill.finished_at} if drill else None,
    }


def _security(space):
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.models_security import MakerspaceSecurityLock

    blocked = MakerspaceMembership.both_tracks().filter(makerspace=space).exclude(
        user__access_status="active").values("user_id").distinct().count()
    return {"blocked_accounts": blocked,
            "locked_settings": MakerspaceSecurityLock.objects.filter(makerspace=space).count()}


def problems(space):
    """Tenant-scope platform problem checks for one servable space (as the dashboard runs them)."""
    if not is_servable(space):
        return []
    from apps.operations.platform_checks import PROBLEM_CHECKS
    from apps.operations.platform_dashboard import tenant_check_context

    now, results = timezone.now(), []
    for check in PROBLEM_CHECKS:
        if check.scope != "tenant":
            continue
        try:
            results.extend(check.evaluate(tenant_check_context(space, check.key), now))
        except Exception:
            results.append({"key": check.key, "status": "warn", "message": "This check could not be completed.",
                            "fix_url": f"/m/{space.slug}/admin/settings/health", "makerspace_id": space.pk})
    return [{key: row.get(key) for key in ("key", "status", "message", "fix_url")} for row in results]


def _managers(space, viewer):
    from apps.accounts.pii_presentation import MASK, pii_visible

    rows = []
    for row in manager_rows(space.pk):
        shown = viewer is None or pii_visible(viewer, space.pk, subject=row.user)
        rows.append({"membership_id": row.pk, "user_id": row.user_id,
                     "name": _who(row.user) if shown else MASK, "email": row.user.email if shown else MASK})
    return rows


def _hosting(space):
    """Decision 236: own vs hosted (never raises; managed_hosting decides)."""
    from apps.managed_hosting.hosting_type import is_hosted, stored_type

    return {"hosting_type": stored_type(space), "hosted": is_hosted(space)}


def card(space, *, detail=False, viewer=None):
    from apps.audit.models import AuditLog

    control = SpaceControlState.objects.select_related(
        "suspended_by", "read_only_by", "scheduled_by").filter(makerspace=space).first()
    usage, peak = _usage(space)
    issues = problems(space)
    data = {
        "id": space.pk, "name": space.name, "slug": space.slug, "public_code": space.public_code,
        "state": state_label(space, control), "lifecycle_state": space.lifecycle_state,
        "created_at": space.created_at, "archived_at": space.archived_at if not is_servable(space) and is_archived(space) else None,
        "suspended": None, "read_only": None, "schedule": None,
        "usage": usage, "usage_peak_percent": peak,
        "last_activity_at": AuditLog.objects.filter(makerspace=space).aggregate(at=Max("created_at"))["at"],
        "backups": _backups(space), "security": _security(space),
        "open_issues": sum(1 for row in issues if row["status"] != "ok"),
        "modules": sorted(space.enabled_modules or []),
        "managers": _managers(space, viewer),
        **_hosting(space),
    }
    if control is not None:
        if control.suspended_at:
            data["suspended"] = {"at": control.suspended_at, "reason": control.suspension_reason,
                                 "by": _who(control.suspended_by)}
        if control.read_only_at:
            data["read_only"] = {"at": control.read_only_at, "reason": control.read_only_reason,
                                 "source": control.read_only_source, "by": _who(control.read_only_by)}
        if control.has_schedule:
            data["schedule"] = {
                "archive_on": control.archive_on, "purge_due_at": control.purge_due_at,
                "purge_grace_days": control.purge_grace_days, "note": control.schedule_note,
                "scheduled_by": _who(control.scheduled_by), "scheduled_at": control.scheduled_at,
                "reminders_sent": [key for key in control.reminders_sent if key != "blocked"],
            }
    from .plan_hook import plan_summary
    plan = plan_summary(space)
    if plan is not False:
        data["plan"] = plan
    if detail:
        data["problems"] = issues
    return data
