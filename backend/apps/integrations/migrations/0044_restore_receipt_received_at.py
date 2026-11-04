"""Repair 0042 receipt times without rewriting conversion history or sending.

0043 remains reserved for the separately approved destructive retirement.
"""
import json

from django.db import migrations
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.makerspaces.secrets import decrypt_value


def restore_received_at(apps, schema_editor):
    alias = schema_editor.connection.alias
    Mapping = apps.get_model("integrations", "NotificationLegacyMapping")
    Receipt = apps.get_model("integrations", "NotificationIngress")
    Legacy = apps.get_model("integrations", "MessagingWebhookEvent")
    mappings = Mapping.objects.using(alias).filter(
        legacy_model="MessagingWebhookEvent", canonical_model="NotificationIngress",
    )
    for mapping in mappings.order_by("pk").iterator(chunk_size=500):
        # The retained original has full database timestamp precision. Its encrypted
        # snapshot is a fallback if an old receipt was already pruned.
        received_at = Legacy.objects.using(alias).filter(pk=mapping.legacy_id).values_list("received_at", flat=True).first()
        if received_at is None and mapping.snapshot:
            original = json.loads(decrypt_value(mapping.snapshot))
            received_at = parse_datetime(original["received_at"])
        if received_at is None or timezone.is_naive(received_at):
            raise RuntimeError("Cannot recover original notification receipt time")
        Receipt.objects.using(alias).filter(pk=mapping.canonical_id).update(received_at=received_at)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0042_notification_history_conversion")]
    operations = [migrations.RunPython(restore_received_at, migrations.RunPython.noop)]
