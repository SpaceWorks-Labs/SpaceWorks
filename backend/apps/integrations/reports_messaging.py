"""Counts-only addressed messaging cohorts; no sender identity enters this projection."""

from django.db.models import Case, CharField, Count, Max, OuterRef, Q, Subquery, Sum, Value, When

from apps.accounts import rbac
from apps.integrations.models import MessagingConsent, MessagingDelivery, MessagingWebhookEvent
from apps.integrations.notification_enums import NotificationFeature
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import module_enabled
from apps.operations.report_fields_hi import COMMUNICATION_COUNTS, COMMUNICATION_FIELDS
from apps.operations.reports_common import report_spaces
from apps.operations.reports_hi_common import buckets, category, ratio, result
from apps.operations.reports_j_common import calendar_range

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
    """Creation cohorts report current observed progress, never inferred timestamps."""
    date_range = calendar_range(date_range, space)
    rows = []
    for channel in CHANNELS:
        if not module_enabled(space, channel):
            continue
        rows.extend(_deliveries(space, channel, grain, date_range))
        events = MessagingWebhookEvent.objects.filter(makerspace=space, channel=channel, state="abandoned")
        for event in buckets(events, "received_at", space, grain, date_range):
            rows.append(messaging_row(channel, period=event["period"].date().isoformat(),
                                      measurement="webhook_receipts", abandoned_webhook_count=event["count"]))
        rows.append(messaging_row(channel, measurement="current_consent_snapshot",
                                  consented_member_count=_consented_members(space, channel)))
    return rows


def _deliveries(space, channel, grain, date_range):
    qs = MessagingDelivery.objects.filter(makerspace=space, channel=channel).annotate(
        safe_feature=category("feature", NotificationFeature.values),
        safe_audience=category("audience", ("member", "staff")),
        source=category("provider_source", ("own", "platform")),
        reason=Case(When(status="skipped", then=category("skip_reason", MessagingDelivery.SkipReason.values)),
                    default=Value("none"), output_field=CharField()),
        segment_basis=Value("not_applicable", output_field=CharField()) if channel != "sms" else Case(
            When(billed_segments__isnull=False, then=Value("billed")),
            default=Value("estimated"), output_field=CharField()),
    )
    measures = {
        "accepted_count": Count("pk", filter=Q(progress_rank__gte=1)),
        "sent_count": Count("pk", filter=Q(progress_rank__gte=2)),
        "delivered_count": Count("pk", filter=Q(progress_rank__gte=3)),
        "read_count": Count("pk", filter=Q(progress_rank=4)),
        "failed_count": Count("pk", filter=Q(status="failed")),
        "skipped_count": Count("pk", filter=Q(status="skipped")),
        "suppressed_count": Count("pk", filter=Q(status="suppressed")),
        "pending_count": Count("pk", filter=Q(status="pending")),
        "sending_count": Count("pk", filter=Q(status="sending")),
        "accepted_only_count": Count("pk", filter=Q(status="accepted")),
        "sent_only_count": Count("pk", filter=Q(status="sent")),
        "delivered_only_count": Count("pk", filter=Q(status="delivered")),
        "attempt_count": Sum("attempts"), "last_activity_at": Max("created_at"),
    }
    if channel == "sms":
        measures.update(estimated_segments=Sum("estimated_segments"), billed_segments=Sum("billed_segments"))
    for cohort in buckets(qs, "created_at", space, grain, date_range,
                          ("safe_feature", "safe_audience", "source", "reason", "segment_basis"), **measures):
        row = messaging_row(channel, period=cohort["period"].date().isoformat(),
                            feature=cohort["safe_feature"], audience=cohort["safe_audience"],
                            provider_source=cohort["source"], skip_reason=cohort["reason"],
                            segment_source=cohort["segment_basis"],
                            triggered_count=cohort["count"], delivery_count=cohort["count"])
        row.update({field: cohort[field] or 0 for field in measures})
        row["segments"] = row["billed_segments"] if row["segment_source"] == "billed" else row["estimated_segments"]
        row.update(delivery_rate_numerator=row["delivered_count"], delivery_rate_denominator=row["accepted_count"],
                   read_rate_numerator=row["read_count"], read_rate_denominator=row["delivered_count"])
        row["delivery_rate"] = ratio(row["delivery_rate_numerator"], row["delivery_rate_denominator"])
        row["read_rate"] = ratio(row["read_rate_numerator"], row["read_rate_denominator"])
        yield row


def _consented_members(space, channel):
    # Phone consent is scoped encrypted PII: compare through the model mapper,
    # never compare ciphertext in SQL or call live_consent once per member.
    members = rbac.scope_notification_policy(MakerspaceMembership.objects.all(), makerspace_id=space.pk).filter(
        status="active", user__is_active=True, user__access_status="active", user__is_tenant_dump_stub=False,
    ).values("user_id")
    latest = MessagingConsent.objects.filter(makerspace=space, channel=channel, user_id=OuterRef("user_id")).order_by("-id")
    consents = MessagingConsent.objects.filter(
        makerspace=space, channel=channel, user_id__in=members, pk=Subquery(latest.values("pk")[:1]),
        action="opted_in", phone_verified_at__isnull=False,
    ).select_related("user")
    return sum(bool(row.user.phone_e164 and row.phone_e164 == row.user.phone_e164
                    and row.phone_verified_at == row.user.phone_verified_at) for row in consents.iterator())


def build_messaging(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id):
        for row in messaging_rows(space, grain=grain, date_range=date_range):
            records.append({**row, **({"makerspace_id": space.pk} if makerspace_id is None else {})})
    return result(COMMUNICATION_FIELDS, records, makerspace_id is None, limit,
                  basis="Current outcomes of creation cohorts; consent is a current snapshot independent of the date filter.",
                  history="Retained rows only. Rejected signatures are not durably recorded and have no measured count.")
