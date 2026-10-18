"""Tenant-attributed native adoption; global app approvals are never tenant rows."""

from datetime import timedelta

from django.db.models import Count, Q

from apps.accounts.models import DeviceGrant, NativeAppRegistration
from apps.accounts.models_activity import DeviceActivityDay
from apps.integrations.models import PushDevice
from apps.makerspaces.platform import module_enabled
from .report_fields_hi import MOBILE_DEVICE_FIELDS
from .reports_common import report_spaces
from .reports_hi_common import buckets, category, result


def build_mobile_devices(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "mobile"):
        if not module_enabled(space, "mobile"):
            continue
        devices = PushDevice.objects.filter(makerspace=space).annotate(
            app_platform=category("device_grant__platform", ("apple", "android")),
            app_environment=category("environment", ("development", "production")),
        )
        dims = ("app_platform", "app_environment")
        for timestamp, metric in (("created_at", "push_registrations"), ("invalidated_at", "push_invalidations")):
            for row in buckets(devices.filter(**{f"{timestamp}__isnull": False}), timestamp,
                               space, grain, date_range, dims):
                _add(records, space, makerspace_id, metric, row)
        for row in devices.order_by().values(*dims, "active").annotate(count=Count("pk")):
            _add(records, space, makerspace_id, "push_devices", row,
                 status="active" if row["active"] else "inactive")
        registrations = NativeAppRegistration.objects.filter(makerspace=space).annotate(
            app_platform=category("platform", ("apple", "android")),
            app_environment=category("environment", ("development", "production")),
        )
        for row in buckets(registrations, "created_at", space, grain, date_range, dims):
            _add(records, space, makerspace_id, "app_registrations", row)
        # A global app's grant belongs here only when validated activity explicitly
        # recorded this tenant. User membership alone is never attribution.
        grants = DeviceGrant.objects.filter(
            Q(registration__makerspace=space) | Q(pk__in=DeviceActivityDay.objects.filter(
                makerspace=space).values("grant_id")),
        ).annotate(app_platform=category("platform", ("apple", "android")),
                   app_environment=category("environment", ("development", "production")),
                   grant_authority=category("authority", ("member", "staff")),
                   grant_status=category("status", ("active", "revoked")))
        for row in grants.order_by().values(*dims, "grant_authority", "grant_status").annotate(count=Count("pk")):
            _add(records, space, makerspace_id, "grants", row,
                 authority=row["grant_authority"], status=row["grant_status"])
        # Group distinct grants at DAILY grain first. Larger buckets sum observed
        # session-days; they never turn last_used_at into invented historical use.
        activity = DeviceActivityDay.objects.filter(makerspace=space)
        if date_range:
            from zoneinfo import ZoneInfo
            for bound, lookup in zip(date_range, ("gte", "lt")):
                if bound is not None:
                    day = bound.astimezone(ZoneInfo(space.timezone)).date()
                    activity = activity.filter(**{f"local_day__{lookup}": day})
        daily = activity.order_by().values("local_day", "platform").annotate(count=Count("grant_id", distinct=True))
        grouped = {}
        for row in daily:
            day = row["local_day"]
            if grain == "week":
                day -= timedelta(days=day.weekday())
            elif grain == "month":
                day = day.replace(day=1)
            elif grain != "day":
                raise ValueError("Unsupported report grain.")
            platform = row["platform"] if row["platform"] in ("apple", "android") else "unknown"
            key = (day, platform)
            grouped[key] = grouped.get(key, 0) + row["count"]
        for (day, platform), count in sorted(grouped.items()):
            _add(records, space, makerspace_id, "active_app_sessions_grants", {
                "period": day, "app_platform": platform, "count": count,
            })
    records.sort(key=lambda row: (row.get("makerspace_id", 0), row["metric"], row["period"] or "", row["platform"], row["environment"], row["authority"], row["status"]))
    return result(MOBILE_DEVICE_FIELDS, records, makerspace_id is None, limit,
                  basis="Push devices and grants are current snapshots; registrations and invalidations are recorded events. Activity is distinct grants per local day; week/month sum session-days.",
                  limitations="Global app registrations are platform-only. Grants require a tenant registration or recorded tenant activity; shared tenant sessions may overlap across spaces.")


def _add(records, space, requested_space, metric, row, *, authority="unknown", status="unknown"):
    period = row.get("period")
    values = dict(period=period.date().isoformat() if hasattr(period, "hour") else period.isoformat() if period else None,
                  metric=metric, platform=row["app_platform"], environment=row.get("app_environment", "unknown"),
                  authority=authority, status=status, count=row["count"])
    if requested_space is None:
        values["makerspace_id"] = space.pk
    records.append(values)
