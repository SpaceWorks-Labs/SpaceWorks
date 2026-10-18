"""Counts-only canonical addressed cohorts; mappings supply inert history only."""
from apps.integrations.models_cutover import NotificationIngress
from apps.makerspaces.platform import module_enabled
from apps.operations.report_fields_hi import COMMUNICATION_COUNTS, COMMUNICATION_FIELDS
from apps.operations.reports_common import apply_range, report_spaces
from apps.operations.reports_hi_common import buckets, ratio, result
from apps.operations.reports_j_common import calendar_range, period
from apps.operations.reports_notification_facts import canonical_deliveries, delivery_facts
from apps.operations.reports_notification_receipts import abandoned_receipts

CHANNELS = ("sms", "whatsapp")


def messaging_row(channel, *, period=None, measurement="delivery_cohort", **dimensions):
    return {
        "period": period, "module_key": channel, "channel": channel,
        "feature": "unknown", "provider_source": "unknown", "platform": "not_applicable",
        "audience": "unknown", "skip_reason": "none", "segment_source": "not_applicable",
        "measurement": measurement, **dict.fromkeys(COMMUNICATION_COUNTS, 0),
        "consented_member_count": None, "last_activity_at": None,
        "success_rate_percent": None, "read_rate_percent": None,
        "delivery_rate": None, "read_rate": None, **dimensions,
    }


def messaging_rows(space, *, grain="day", date_range=None):
    date_range = calendar_range(date_range, space)
    rows = []
    for channel in CHANNELS:
        if not module_enabled(space, channel):
            continue
        qs = apply_range(canonical_deliveries().filter(makerspace=space, channel=channel), "created_at", date_range)
        rows.extend(cohort_rows(space, delivery_facts(qs), grain=grain))
        # Held receipts remain recoverable; they are not abandoned events.
        receipts = NotificationIngress.objects.filter(makerspace=space, channel=channel, state="held")
        for receipt in buckets(receipts, "received_at", space, grain, date_range):
            rows.append(messaging_row(channel, period=receipt["period"].date().isoformat(),
                                      measurement="webhook_receipts", held_webhook_count=receipt["count"]))
        for bucket, count in abandoned_receipts(space, channel, grain, date_range).items():
            rows.append(messaging_row(channel, period=bucket, measurement="webhook_receipts",
                                      abandoned_webhook_count=count))
        from apps.operations.reports_notification_consent import consented_members
        rows.append(messaging_row(channel, measurement="current_consent_snapshot",
                                  consented_member_count=consented_members(space, channel)))
    return rows


def cohort_rows(space, facts, *, grain="day"):
    """Exclusive current outcomes and cumulative progress of creation cohorts."""
    from .notification_enums import NotificationFeature
    groups = {}
    for fact in facts:
        channel = fact["channel"]
        feature, audience = fact["envelope__feature"], fact["envelope__audience"]
        source = fact["provider_source"]
        basis = "billed" if fact["billed_segments"] is not None else "estimated"
        key = (period(fact["created_at"], grain, space), channel,
               feature if feature in NotificationFeature.values else "unknown",
               audience if audience in ("member", "staff", "requester") else "unknown",
               source if source in ("own", "platform") else "unknown",
               fact["skip_reason"], basis if channel == "sms" else "not_applicable")
        row = groups.setdefault(key, messaging_row(channel, period=key[0], feature=key[2],
            audience=key[3], provider_source=key[4], skip_reason=key[5], segment_source=key[6],
            module_key="mobile" if channel == "native_push" else "notifications" if channel == "in_app" else channel))
        row["triggered_count"] += 1
        row["delivery_count"] += 1
        row["attempt_count"] += fact["attempt_count"]
        for name, threshold in (("accepted_count", 1), ("sent_count", 2), ("delivered_count", 3)):
            row[name] += fact["progress"] >= threshold
        row["read_count"] += fact["progress"] == 4
        column = {"accepted": "accepted_only_count", "sent": "sent_only_count",
                  "delivered": "delivered_only_count"}.get(fact["status"], fact["status"] + "_count")
        if column in row and column != "read_count":
            row[column] += 1
        if channel == "sms":
            row["estimated_segments"] += fact["estimated_segments"]
            row["billed_segments"] += fact["billed_segments"] or 0
            row["segments"] += fact["billed_segments"] if basis == "billed" else fact["estimated_segments"]
        row["last_activity_at"] = max(row["last_activity_at"] or fact["created_at"], fact["created_at"],
            *(fact[state + "_at"] or fact["created_at"] for state in ("accepted", "sent", "delivered", "read", "failed")))
    for row in groups.values():
        row.update(delivery_rate_numerator=row["delivered_count"], delivery_rate_denominator=row["accepted_count"],
                   read_rate_numerator=row["read_count"], read_rate_denominator=row["delivered_count"])
        row["delivery_rate"] = ratio(row["delivered_count"], row["accepted_count"])
        row["read_rate"] = ratio(row["read_count"], row["delivered_count"])
    return list(groups.values())


def build_messaging(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id):
        for row in messaging_rows(space, grain=grain, date_range=date_range):
            records.append({**row, **({"makerspace_id": space.pk} if makerspace_id is None else {})})
    return result(COMMUNICATION_FIELDS, records, makerspace_id is None, limit,
                  basis="Canonical creation cohorts including mapped inert history; consent is a current snapshot.",
                  history="Held attempts/receipts are unresolved. Abandoned receipt counts are original legacy snapshots, not current processing outcomes. Reports never process callbacks or send queues.")
