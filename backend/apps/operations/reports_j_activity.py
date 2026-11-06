"""Counts and deliberately separate, tenant-only person rankings."""

from django.utils.translation import gettext
from collections import defaultdict
import re
from zoneinfo import ZoneInfo

from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.operations.report_types import ReportNotFound
from apps.operations.report_fields_j import PRESENCE_FIELDS, AUDIT_FIELDS, HOUR_FIELDS, PERSON_FIELDS
from apps.operations.reports_common import apply_range
from apps.operations.reports_j_common import area_spaces, calendar_range, period, result
from apps.presence.models import PresenceSession



def _presence(space, date_range):
    return apply_range(PresenceSession.objects.filter(makerspace=space), "started_at", calendar_range(date_range, space)).values(
        "member_id", "started_at", "ended_at", "expires_at",
    ).iterator()


def _duration(row, now):
    end = min(row["expires_at"], row["ended_at"] or row["expires_at"], now)
    return max(0, (end - row["started_at"]).total_seconds())


def build_presence_activity(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records, now = [], timezone.now()
    for space in area_spaces(makerspace_id):
        groups = {}
        for row in _presence(space, date_range):
            key = period(row["started_at"], grain, space)
            state = groups.setdefault(key, {"period": key, "visits": 0, "declared_presence_seconds": 0, "_visitors": set()})
            state["visits"] += 1
            state["declared_presence_seconds"] += _duration(row, now)
            state["_visitors"].add(row["member_id"])
        for row in groups.values():
            row.update(makerspace_id=space.pk, unique_visitors=len(row["_visitors"]),
                       average_declared_presence_seconds=row["declared_presence_seconds"] / row["visits"])
            records.append(row)
    records.sort(key=lambda r: (r["period"], r["makerspace_id"]))
    return result(PRESENCE_FIELDS, records, makerspace_id, limit, definition="Declared presence duration; sessions grouped by start time, capped at observed time.")


def build_audit_activity(makerspace_id, *, limit=None, date_range=None, grain="day"):
    from apps.operations.reports_common import period_expression
    records = []
    for space in area_spaces(makerspace_id):
        qs = apply_range(AuditLog.objects.filter(makerspace=space), "created_at", calendar_range(date_range, space))
        rows = qs.order_by().annotate(period=period_expression("created_at", grain, makerspace=space)).values("period", "action").annotate(count=Count("pk"))
        groups = defaultdict(int)
        for row in rows:
            groups[(row["period"].date().isoformat(), _action_label(row["action"]))] += row["count"]
        records.extend({"makerspace_id": space.pk, "period": bucket,
                        "action": action, "count": count} for (bucket, action), count in groups.items())
    records.sort(key=lambda r: (-r["count"], r["period"], r["action"], r["makerspace_id"]))
    return result(AUDIT_FIELDS, records, makerspace_id, limit)


def _action_label(action):
    from apps.audit.presentation_catalog import PRESENTATION_CATALOG
    # Unknown action text is not an allowlisted dimension and could contain PII.
    # Known credential-operation names use neutral labels so disclosure guards
    # can still reject actual credential-shaped values everywhere in the report.
    if action not in PRESENTATION_CATALOG:
        return "unrecognized"
    return re.sub(r"secret|token|password|private[_ -]?key|webhook[_ -]?url|api[_ -]?key|smtp", "credential", action, flags=re.I)


def _tenant(makerspace_id):
    if makerspace_id is None:
        raise ReportNotFound()


def _ranking_authority(actor, makerspace_id, action):
    _tenant(makerspace_id)
    if not rbac.can(actor, action, makerspace_id) or not rbac.can(actor, rbac.Action.VIEW_AUDIT, makerspace_id):
        raise PermissionDenied(gettext("Person rankings require domain authority and audit access."))


def build_presence_top_visitors(makerspace_id, *, actor=None, limit=None, date_range=None):
    _ranking_authority(actor, makerspace_id, rbac.Action.MANAGE_MEMBERS)
    groups, now = {}, timezone.now()
    for space in area_spaces(makerspace_id):
        for row in _presence(space, date_range):
            state = groups.setdefault(row["member_id"], {"person_id": row["member_id"], "count": 0, "declared_presence_seconds": 0})
            state["count"] += 1
            state["declared_presence_seconds"] += _duration(row, now)
    return result(PERSON_FIELDS, sorted(groups.values(), key=lambda r: (-r["count"], r["person_id"])), makerspace_id, limit)


def build_audit_top_actors(makerspace_id, *, actor=None, limit=None, date_range=None):
    _ranking_authority(actor, makerspace_id, rbac.Action.VIEW_AUDIT)
    spaces = area_spaces(makerspace_id)
    date_range = calendar_range(date_range, spaces[0]) if spaces else date_range
    qs = apply_range(AuditLog.objects.filter(makerspace_id=makerspace_id, actor__isnull=False), "created_at", date_range)
    rows = qs.order_by().values("actor_id").annotate(count=Count("pk")).order_by("-count", "actor_id")
    return result(PERSON_FIELDS, [{"person_id": r["actor_id"], "count": r["count"], "declared_presence_seconds": None} for r in rows], makerspace_id, limit)


def _hours(makerspace_id, *, presence, limit, date_range):
    # Local hour-of-week has no single calendar across organizations.
    _tenant(makerspace_id)
    groups, now = defaultdict(lambda: {"count": 0, "declared_presence_seconds": 0}), timezone.now()
    for space in area_spaces(makerspace_id):
        date_range = calendar_range(date_range, space)
        zone = ZoneInfo(space.timezone)
        if presence:
            # Occupancy is accumulated over each overlapping actual hour, rather
            # than pretending that arrival counts measure occupancy.
            qs = PresenceSession.objects.filter(makerspace=space)
            if date_range:
                start, end = date_range
                if start:
                    qs = qs.filter(expires_at__gt=start)
                if end:
                    qs = qs.filter(started_at__lt=end)
            from datetime import timedelta
            for row in qs.values("started_at", "ended_at", "expires_at").iterator():
                cursor = row["started_at"]
                end_at = min(row["ended_at"] or row["expires_at"], row["expires_at"], now)
                if date_range:
                    if date_range[0]:
                        cursor = max(cursor, date_range[0])
                    if date_range[1]:
                        end_at = min(end_at, date_range[1])
                while cursor < end_at:
                    local = cursor.astimezone(zone)
                    boundary = min(end_at, cursor + timedelta(seconds=3600 - local.minute * 60 - local.second - local.microsecond / 1e6))
                    state = groups[(local.weekday(), local.hour)]
                    state["count"] += 1
                    state["declared_presence_seconds"] += (boundary - cursor).total_seconds()
                    cursor = boundary
        else:
            from django.db.models.functions import ExtractHour, ExtractIsoWeekDay
            qs = apply_range(AuditLog.objects.filter(makerspace=space), "created_at", date_range)
            hours = qs.order_by().annotate(weekday=ExtractIsoWeekDay("created_at", tzinfo=zone), hour=ExtractHour("created_at", tzinfo=zone))
            for row in hours.values("weekday", "hour").annotate(count=Count("pk")):
                groups[(row["weekday"] - 1, row["hour"])]["count"] += row["count"]
    rows = [{"weekday": day, "hour": hour, **state} for (day, hour), state in sorted(groups.items())]
    return result(HOUR_FIELDS, rows, makerspace_id, limit, definition="Local hour-of-week; presence seconds measure declared occupancy, not verified attendance.")


def build_presence_activity_hours(makerspace_id, *, limit=None, date_range=None):
    return _hours(makerspace_id, presence=True, limit=limit, date_range=date_range)


def build_audit_activity_hours(makerspace_id, *, limit=None, date_range=None):
    return _hours(makerspace_id, presence=False, limit=limit, date_range=date_range)
