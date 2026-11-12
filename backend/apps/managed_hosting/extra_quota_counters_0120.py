"""Counters for the 0.12.0 module-by-module limit keys (decision 328a); same rules as ``extra_quota_counters``.

Monthly counters use the UTC calendar month and count cancelled rows too (churn cannot reset a quota); the
others count what still exists. Every function reads rows that already exist: no new table.
"""
from django.db.models import Sum

from .extra_quota_counters import month_start


def hardware_requests_monthly(space):
    from apps.hardware_requests.models import HardwareRequest
    return HardwareRequest.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def stock_transfers_monthly(space):
    from apps.operations.models import StockTransfer
    return StockTransfer.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def stocktake_sessions_monthly(space):
    from apps.operations.models import StocktakeSession
    return StocktakeSession.objects.filter(makerspace=space, started_at__gte=month_start()).count()


def shelf_checks_monthly(space):
    from apps.devices.models import ShelfCheck
    return ShelfCheck.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def reimbursement_claims_monthly(space):
    from apps.event_reimbursements.claim_models import ReimbursementClaim
    return ReimbursementClaim.objects.filter(event__makerspace=space, created_at__gte=month_start()).count()


def public_page_assets(space):
    from apps.makerspaces.models import MakerspacePublicPageAsset
    return MakerspacePublicPageAsset.objects.filter(page__makerspace=space).count()


def scheduled_reports(space):
    from apps.operations.models_report_schedules import ReportSchedule
    return ReportSchedule.objects.filter(makerspace=space, is_active=True).count()


def adapter_media_bytes(space):
    """Bytes of adapter timelapses, previews and bundles still kept (pending uploads included, purged ones not)."""
    from apps.devices.models import AdapterArtifact
    rows = AdapterArtifact.objects.filter(makerspace=space).exclude(status="purged")
    return int(rows.aggregate(total=Sum("size_bytes"))["total"] or 0)


def adapter_telemetry_points(space):
    """Telemetry samples (raw and rollups) the space's adapters hold; the retention sweep keeps this bounded."""
    from apps.devices.models import AdapterTelemetryPoint
    return AdapterTelemetryPoint.objects.filter(binding__makerspace=space).count()


def anthias_players(space):
    from apps.presence.models_anthias import AnthiasPlayer
    return AnthiasPlayer.objects.filter(makerspace=space).count()


COUNTERS_0120 = {fn.__name__: fn for fn in (
    hardware_requests_monthly, stock_transfers_monthly, stocktake_sessions_monthly, shelf_checks_monthly,
    reimbursement_claims_monthly,
    public_page_assets, scheduled_reports, adapter_media_bytes, adapter_telemetry_points, anthias_players)}
