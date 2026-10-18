"""Retained physical email/room outcomes and optional inbox read measurements."""
from django.db.models import Count, Max, Q, Sum

from apps.integrations.models import EmailLog, NotificationDeliveryLog
from apps.integrations.notification_enums import NotificationFeature
from apps.integrations.reports_messaging import messaging_row
from apps.makerspaces.platform import module_enabled
from .reports_hi_common import buckets, category

CHAT = ("telegram", "slack", "mattermost", "discord", "webhook")


def ledger_rows(space, grain, date_range):
    rows = []
    if module_enabled(space, "email"):
        rows.extend(_email(space, grain, date_range))
    for channel in CHAT:
        if not module_enabled(space, channel):
            continue
        qs = NotificationDeliveryLog.objects.filter(makerspace=space, channel=channel).annotate(
            safe_feature=category("feature", NotificationFeature.values))
        for cohort in buckets(qs, "created_at", space, grain, date_range, ("safe_feature",),
            pending=Count("pk", filter=Q(status="pending")), sending=Count("pk", filter=Q(status="sending")),
            sent=Count("pk", filter=Q(status="sent")), failed=Count("pk", filter=Q(status="failed")),
            skipped=Count("pk", filter=Q(status="skipped")), attempts=Sum("attempts"), last=Max("created_at")):
            rows.append(messaging_row(channel, period=cohort["period"].date().isoformat(),
                feature=cohort["safe_feature"], audience="staff", provider_source="own",
                triggered_count=cohort["count"], delivery_count=cohort["count"], attempt_count=cohort["attempts"] or 0,
                sent_count=cohort["sent"], sent_only_count=cohort["sent"], failed_count=cohort["failed"],
                pending_count=cohort["pending"], sending_count=cohort["sending"],
                skipped_count=cohort["skipped"], last_activity_at=cohort["last"]))
    if module_enabled(space, "notifications"):
        rows.extend(_inbox(space, grain, date_range))
    return rows


def _email(space, grain, date_range):
    qs = EmailLog.objects.filter(makerspace=space).annotate(source=category("provider_source", ("platform", "own")))
    suppressed = Q(status="skipped", error="email_address_suppressed")
    for cohort in buckets(qs, "created_at", space, grain, date_range, ("source",),
        pending=Count("pk", filter=Q(status="pending")), sending=Count("pk", filter=Q(status="sending")),
        sent=Count("pk", filter=Q(status="sent")), failed=Count("pk", filter=Q(status="failed")),
        suppressed=Count("pk", filter=suppressed), skipped=Count("pk", filter=Q(status="skipped") & ~suppressed),
        attempts=Sum("attempts"), last=Max("created_at")):
        yield messaging_row("email", period=cohort["period"].date().isoformat(), feature="email",
            provider_source=cohort["source"], triggered_count=cohort["count"], delivery_count=cohort["count"],
            attempt_count=cohort["attempts"] or 0, sent_count=cohort["sent"], sent_only_count=cohort["sent"],
            pending_count=cohort["pending"], sending_count=cohort["sending"],
            failed_count=cohort["failed"], suppressed_count=cohort["suppressed"], skipped_count=cohort["skipped"],
            last_activity_at=cohort["last"])
    for timestamp, metric in (("bounced_at", "bounced_count"), ("complained_at", "complained_count")):
        for cohort in buckets(qs.filter(**{f"{timestamp}__isnull": False}), timestamp, space, grain, date_range,
                              ("source",), last=Max(timestamp)):
            yield messaging_row("email", period=cohort["period"].date().isoformat(), feature="email",
                provider_source=cohort["source"], last_activity_at=cohort["last"], **{metric: cohort["count"]})


def _inbox(space, grain, date_range):
    from apps.notifications.models_inbox import NotificationInboxRow
    qs = NotificationInboxRow.objects.filter(makerspace=space).annotate(
        safe_feature=category("feature", NotificationFeature.values))
    read = Q(read_at__isnull=False)
    if date_range and date_range[1] is not None:
        read &= Q(read_at__lt=date_range[1])
    for cohort in buckets(qs, "created_at", space, grain, date_range, ("safe_feature",),
        reads=Count("pk", filter=read), last=Max("created_at")):
        yield messaging_row("in_app", module_key="notifications", period=cohort["period"].date().isoformat(),
            feature=cohort["safe_feature"], inbox_created_count=cohort["count"], inbox_read_count=cohort["reads"],
            unread_count=cohort["count"] - cohort["reads"], last_activity_at=cohort["last"])
