"""Canonical personal legs plus retained room/email and per-device outcome ledgers."""
from django.db.models import Count, Max, Q, Sum

from apps.integrations.reports_messaging import cohort_rows, messaging_row, messaging_rows
from apps.makerspaces.platform import module_enabled
from apps.operations.report_fields_hi import COMMUNICATION_FIELDS, COMMUNICATION_GROUPS
from apps.operations.reports_common import apply_range, report_spaces
from apps.operations.reports_hi_common import buckets, category, percent, result
from apps.operations.reports_j_common import calendar_range
from apps.operations.reports_notification_facts import canonical_deliveries, delivery_facts
from apps.operations.reports_push_facts import push_querysets
from apps.operations.reports_communications_ledgers import CHAT, ledger_rows


def build_communications_health(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id):
        local_range = calendar_range(date_range, space)
        channels = [channel for channel in CHAT if module_enabled(space, channel)]
        qs = apply_range(canonical_deliveries().filter(makerspace=space, channel__in=channels), "created_at", local_range)
        rows = [*ledger_rows(space, grain, local_range), *cohort_rows(space, delivery_facts(qs), grain=grain),
                *messaging_rows(space, grain=grain, date_range=local_range)]
        if module_enabled(space, "mobile"):
            rows.extend(_push(space, grain, local_range))
        for row in rows:
            row["success_rate_percent"] = percent(row["sent_count"], row["delivery_count"])
            row["read_rate_percent"] = (percent(row["read_rate_numerator"], row["read_rate_denominator"])
                if row["channel"] in ("sms", "whatsapp") else percent(row["inbox_read_count"], row["inbox_created_count"]))
            if makerspace_id is None:
                row["makerspace_id"] = space.pk
            records.append(row)
    records.sort(key=lambda row: (row.get("makerspace_id", 0), *(str(row.get(f) or "") for f in COMMUNICATION_GROUPS)))
    return result(COMMUNICATION_FIELDS, records, makerspace_id is None, limit,
        basis="Canonical creation cohorts plus mapped inert history; email and push use provider/device ledgers once. Inbox reads use window end; consent is a current member snapshot.",
        history="Held attempts/receipts are unresolved; abandoned receipts are original legacy observations, not current state. Segments prefer billed values including zero. Private content and sender identifiers are excluded.")


def _push(space, grain, date_range):
    rows = []
    for qs, tenant, feature, audience in push_querysets([space.pk]):
        qs = qs.annotate(safe_feature=category(feature, _features()),
            source=category("provider_source", ("platform", "own")),
            device_platform=category("platform", ("apple", "android")))
        dimensions = ["safe_feature", "source", "device_platform"]
        if audience:
            qs = qs.annotate(safe_audience=category(audience, ("staff", "member", "requester")))
            dimensions.append("safe_audience")
        invalid = Q(status="failed", last_error="invalid_token")
        for cohort in buckets(qs, "created_at", space, grain, date_range, dimensions,
            sent=Count("pk", filter=Q(status="sent")), failed=Count("pk", filter=Q(status="failed") & ~invalid),
            invalid=Count("pk", filter=invalid), skipped=Count("pk", filter=Q(status="skipped")),
            pending=Count("pk", filter=Q(status="pending")), sending=Count("pk", filter=Q(status="sending")),
            held=Count("pk", filter=Q(status="held")), attempts=Sum("attempts"), last=Max("created_at")):
            rows.append(messaging_row("native_push", module_key="mobile", period=cohort["period"].date().isoformat(),
                feature=cohort["safe_feature"], provider_source=cohort["source"], platform=cohort["device_platform"],
                audience=cohort.get("safe_audience", "staff"), triggered_count=cohort["count"], delivery_count=cohort["count"],
                attempt_count=cohort["attempts"] or 0, sent_count=cohort["sent"], sent_only_count=cohort["sent"],
                failed_count=cohort["failed"], invalid_count=cohort["invalid"], skipped_count=cohort["skipped"],
                pending_count=cohort["pending"], sending_count=cohort["sending"], held_count=cohort["held"], last_activity_at=cohort["last"]))
    return rows


def _features():
    from apps.integrations.notification_enums import NotificationFeature
    return NotificationFeature.values
