"""Original abandoned receipt observations retained by the conversion ledger."""
import json
import logging

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integrations.models_cutover import NotificationLegacyMapping
from apps.makerspaces.secrets import decrypt_value
from .reports_j_common import period

logger = logging.getLogger(__name__)


def abandoned_receipts(space, channel, grain, date_range):
    groups = {}
    mappings = NotificationLegacyMapping.objects.filter(makerspace=space,
        legacy_model="MessagingWebhookEvent", canonical_model="NotificationIngress")
    for snapshot in mappings.values_list("snapshot", flat=True).iterator(chunk_size=500):
        try:
            original = json.loads(decrypt_value(snapshot))
            if original.get("channel") != channel or original.get("state") != "abandoned":
                continue
            stamp = parse_datetime(original.get("received_at") or "")
            if stamp is None or timezone.is_naive(stamp):
                continue
        except Exception as exc:
            logger.error("notification_report_receipt_history_unreadable", extra={"error_type": type(exc).__name__})
            continue
        if date_range and ((date_range[0] and stamp < date_range[0]) or (date_range[1] and stamp >= date_range[1])):
            continue
        bucket = period(stamp, grain, space)
        groups[bucket] = groups.get(bucket, 0) + 1
    return groups
