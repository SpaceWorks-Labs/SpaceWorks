"""Communication outcomes from recorded delivery facts, never message content."""

from django.db.models import Count, Max, Q, Sum

from apps.integrations.models import EmailLog, NotificationDeliveryLog, PushDeliveryAttempt
from apps.makerspaces.platform import module_enabled
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from apps.operations.report_fields_hi import (
    COMMUNICATION_COUNTS, COMMUNICATION_FIELDS, COMMUNICATION_GROUPS,
)
from apps.operations.reports_common import report_spaces
from apps.operations.reports_hi_common import buckets, category, percent, result
from apps.operations.reports_j_common import calendar_range
from apps.integrations.reports_messaging import messaging_rows

FIELDS = COMMUNICATION_FIELDS
CHANNELS = ("telegram", "slack", "mattermost", "discord", "webhook")


def build_communications_health(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id):
        local_range = calendar_range(date_range, space)
        groups = {}
        if module_enabled(space, "email"):
            _email(space, groups, grain, local_range)
        for channel in CHANNELS:
            if module_enabled(space, channel):
                qs = NotificationDeliveryLog.objects.filter(makerspace=space, channel=channel)
                _delivery(qs, space, groups, grain, local_range, channel, channel)
        if module_enabled(space, "mobile"):
            staff = PushDeliveryAttempt.objects.filter(delivery_log__makerspace=space)
            _delivery(staff, space, groups, grain, local_range, "mobile", "native_push", push=True)
            if module_enabled(space, "notifications"):
                member = MemberPushDelivery.objects.filter(inbox_row__makerspace=space)
                _delivery(member, space, groups, grain, local_range, "mobile", "native_push", push=True, member=True)
        if module_enabled(space, "notifications"):
            _inbox(space, groups, grain, local_range)
        for row in [*groups.values(), *messaging_rows(space, grain=grain, date_range=local_range)]:
            row["success_rate_percent"] = percent(row["sent_count"], row["delivery_count"])
            row["read_rate_percent"] = (percent(row["read_rate_numerator"], row["read_rate_denominator"])
                                        if row["channel"] in ("sms", "whatsapp") else
                                        percent(row["inbox_read_count"], row["inbox_created_count"]))
            if makerspace_id is None:
                row["makerspace_id"] = space.pk
            records.append(row)
    records.sort(key=lambda row: (row.get("makerspace_id", 0), *(str(row.get(f) or "") for f in COMMUNICATION_GROUPS)))
    return result(FIELDS, records, makerspace_id is None, limit,
                  basis="Delivery creation cohorts show current progress; inbox reads are measured at window end. Bounces/complaints use event time. Consent is a current snapshot; segments prefer billed over estimated, labelled by segment_source.",
                  history="Retained rows only; unrecorded dimensions are unknown. Rejected messaging signatures have no durable count. Push retries are attempts, not extra deliveries.")


def _add(groups, period, module, channel, feature, provider="unknown", platform="unknown", last=None, **counts):
    key = (period.date().isoformat(), module, channel, feature, provider, platform,
           "not_applicable", "none", "not_applicable", "delivery_cohort")
    row = groups.setdefault(key, {**dict(zip(COMMUNICATION_GROUPS, key)),
                                  **dict.fromkeys(COMMUNICATION_COUNTS, 0), "last_activity_at": None})
    for field, value in counts.items():
        row[field] += value or 0
    if last is not None and (row["last_activity_at"] is None or last > row["last_activity_at"]):
        row["last_activity_at"] = last


def _email(space, groups, grain, date_range):
    qs = EmailLog.objects.filter(makerspace=space).annotate(
        source=category("provider_source", ("platform", "own")),
    )
    dimensions = ("source",)
    measures = dict(
        sent=Count("pk", filter=Q(status="sent")), failed=Count("pk", filter=Q(status="failed")),
        suppressed=Count("pk", filter=Q(status="skipped", error="email_address_suppressed")),
        skipped=Count("pk", filter=Q(status="skipped") & ~Q(error="email_address_suppressed")),
        attempts=Sum("attempts"), last=Max("created_at"),
    )
    for row in buckets(qs, "created_at", space, grain, date_range, dimensions, **measures):
        _add(groups, row["period"], "email", "email", "email", row["source"], last=row["last"],
             triggered_count=row["count"], delivery_count=row["count"], attempt_count=row["attempts"],
             sent_count=row["sent"], failed_count=row["failed"], suppressed_count=row["suppressed"], skipped_count=row["skipped"])
    for timestamp, metric in (("bounced_at", "bounced_count"), ("complained_at", "complained_count")):
        for row in buckets(qs.filter(**{f"{timestamp}__isnull": False}), timestamp, space,
                           grain, date_range, dimensions, last=Max(timestamp)):
            _add(groups, row["period"], "email", "email", "email", row["source"], last=row["last"],
                 **{metric: row["count"]})


def _delivery(qs, space, groups, grain, date_range, module, channel, *, push=False, member=False):
    if push:
        feature = "inbox_row__feature" if member else "delivery_log__feature"
        qs = qs.annotate(source=category("provider_source", ("platform", "own")),
                         device_platform=category("platform", ("apple", "android")))
        dimensions = (feature, "source", "device_platform")
    else:
        feature, dimensions = "feature", ("feature",)
    # Invalid outcomes are disjoint from other failures, and are never inferred
    # from a device's later invalidation (which would rewrite old delivery history).
    invalid = Q(status="failed", last_error="invalid_token") if push else Q(pk__isnull=True)
    measures = dict(sent=Count("pk", filter=Q(status="sent")),
                    failed=Count("pk", filter=Q(status="failed") & ~invalid),
                    invalid=Count("pk", filter=invalid), skipped=Count("pk", filter=Q(status="skipped")),
                    attempts=Sum("attempts"), last=Max("created_at"))
    for row in buckets(qs, "created_at", space, grain, date_range, dimensions, **measures):
        _add(groups, row["period"], module, channel, _feature(row[feature]),
             row["source"] if push else "own", row["device_platform"] if push else "unknown",
             last=row["last"], triggered_count=row["count"], delivery_count=row["count"],
             attempt_count=row["attempts"], sent_count=row["sent"], failed_count=row["failed"],
             invalid_count=row["invalid"], skipped_count=row["skipped"])


def _feature(value):
    from apps.integrations.notification_enums import NotificationFeature
    return value if value in NotificationFeature.values else "unknown"


def _inbox(space, groups, grain, date_range):
    qs = NotificationInboxRow.objects.filter(makerspace=space)
    read = Q(read_at__isnull=False)
    if date_range and date_range[1] is not None:
        read &= Q(read_at__lt=date_range[1])
    for row in buckets(qs, "created_at", space, grain, date_range, ("feature",),
                       reads=Count("pk", filter=read), last=Max("created_at")):
        _add(groups, row["period"], "notifications", "in_app", _feature(row["feature"]),
             last=row["last"], inbox_created_count=row["count"], inbox_read_count=row["reads"],
             unread_count=row["count"] - row["reads"])
