"""Platform-only source projections for the 1f-3 mobile/platform builders.

These are helpers, not tenant report keys. An attestation outcome ledger has no
tenant identity; it must never be joined to a person or app to invent one.
"""

from django.db.models import Count

from apps.accounts.models import NativeAppRegistration
from apps.accounts.models_activity import AttestationVerificationLog, DeviceActivityDay
from .platform_scope import platform_analytics_spaces, require_platform_context
from .report_types import ReportResult
from .reports_common import apply_range, period_expression
from .reports_hi_common import category


def global_app_registrations(*, platform_context=None, date_range=None, grain="day"):
    require_platform_context(platform_context)
    qs = NativeAppRegistration.objects.filter(makerspace__isnull=True)
    qs = apply_range(qs, "created_at", date_range).annotate(
        app_platform=category("platform", ("apple", "android")),
        app_environment=category("environment", ("development", "production")),
        period=period_expression("created_at", grain),
    )
    rows = [dict(period=row["period"].date().isoformat(), platform=row["app_platform"],
                 environment=row["app_environment"], count=row["count"])
            for row in qs.order_by("period", "app_platform", "app_environment")
            .values("period", "app_platform", "app_environment").annotate(count=Count("pk"))]
    return ReportResult(("period", "platform", "environment", "count"), rows)


def platform_attestation_outcomes(*, platform_context=None, date_range=None, grain="day"):
    require_platform_context(platform_context)
    qs = apply_range(AttestationVerificationLog.objects.all(), "created_at", date_range).annotate(
        app_platform=category("platform", ("apple", "android")),
        verification_mode=category("mode", ("external", "in_process", "development_insecure", "unavailable")),
        verification_outcome=category("outcome", ("sent", "failed", "skipped")),
        period=period_expression("created_at", grain),
    )
    rows = [dict(period=row["period"].date().isoformat(), platform=row["app_platform"],
                 mode=row["verification_mode"], outcome=row["verification_outcome"], count=row["count"])
            for row in qs.order_by("period", "app_platform", "verification_mode", "verification_outcome")
            .values("period", "app_platform", "verification_mode", "verification_outcome").annotate(count=Count("pk"))]
    return ReportResult(("period", "platform", "mode", "outcome", "count"), rows)


def platform_active_app_sessions(*, platform_context=None, date_range=None):
    """Distinct grants per recorded day, deduplicated across visible tenants/NULL."""
    from django.db.models import Q
    spaces = platform_analytics_spaces(require_platform_context(platform_context))
    qs = DeviceActivityDay.objects.filter(Q(makerspace__in=spaces) | Q(makerspace__isnull=True))
    if date_range:
        for bound, lookup in zip(date_range, ("gte", "lt")):
            if bound is not None:
                qs = qs.filter(**{f"local_day__{lookup}": bound.date()})
    rows = [dict(period=row["local_day"].isoformat(), count=row["count"])
            for row in qs.order_by("local_day").values("local_day").annotate(count=Count("grant_id", distinct=True))]
    return ReportResult(("period", "count"), rows)
