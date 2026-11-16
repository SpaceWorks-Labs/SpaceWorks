"""Delivery facts augment the existing module health inventory."""

from django.db.models import Count

from apps.makerspaces.platform import module_enabled
from apps.operations.models_report_schedules import ReportDelivery
from apps.operations.reports_common import apply_range, period_expression
from apps.operations.reports_j_common import area_spaces, calendar_range, rate, result
from apps.operations.report_fields_j import HEALTH_FIELDS as FIELDS



def build_module_operational_health(makerspace_id, *, limit=None, date_range=None, grain="day"):
    from apps.operations.reports_module_health import build_module_operational_health as legacy_health
    records = []
    for space in area_spaces(makerspace_id):
        window = calendar_range(date_range, space)
        for row in legacy_health(space.pk, date_range=window).records:
            records.append({**row, **({"makerspace_id": space.pk} if makerspace_id is None else {})})
        sources = [("reports", "report_delivery", ReportDelivery.objects.filter(schedule__makerspace=space), "status", {"sent"}, {"failed"})]
        from apps.integrations.models_contract import NotificationDelivery
        for channel in ("sms", "whatsapp"):
            if module_enabled(space, channel):
                sources.append((channel, "notification_delivery",
                    NotificationDelivery.objects.filter(makerspace=space, channel=channel), "state",
                    {"accepted", "sent", "delivered", "read"}, {"failed"}))
        for module, kind, qs, status_field, successes, failures in sources:
            qs = apply_range(qs, "created_at", window)
            groups = {}
            for row in qs.order_by().annotate(period=period_expression("created_at", grain, makerspace=space)).values("period", status_field).annotate(count=Count("pk")):
                bucket = row["period"].date().isoformat()
                state = groups.setdefault(bucket, {"delivery_count": 0, "success_count": 0, "failure_count": 0})
                state["delivery_count"] += row["count"]
                if row[status_field] in successes:
                    state["success_count"] += row["count"]
                if row[status_field] in failures:
                    state["failure_count"] += row["count"]
            for bucket, state in sorted(groups.items()):
                records.append({**({"makerspace_id": space.pk} if makerspace_id is None else {}),
                                "module_key": module, "period": bucket,
                                "delivery_kind": kind, "enabled": True, "runtime_available": True,
                                "coverage_kind": "delivery", "activity_count": state["delivery_count"], **state,
                                "success_rate_percent": rate(state["success_count"], state["success_count"] + state["failure_count"])})
    return result(FIELDS, records, makerspace_id, limit,
                  definition="Delivery creation cohorts with current outcomes; rates use terminal outcomes. Archive expiry/offsite retention deletion follows successful delivery.")
