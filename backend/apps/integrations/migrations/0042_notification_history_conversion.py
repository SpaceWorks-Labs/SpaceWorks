"""CONVERT checkpoint; refuses populated installations without a drained barrier."""
from django.db import migrations
from ._notification_conversion_v1 import copy


def refuse_populated_reverse(registry, schema_editor):
    """Only an unpopulated copy (fresh/test databases) may be unapplied.

    Every copied legacy row commits a legacy mapping. Once one exists, reversal
    could resend history or invent authority, so populated installations refuse.
    """
    Mapping = registry.get_model("integrations", "NotificationLegacyMapping")
    if Mapping.objects.using(schema_editor.connection.alias).exists():
        raise RuntimeError("0042 history conversion is irreversible once legacy rows were copied")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("integrations", "0041_notification_cutover_expansion")]
    operations = [migrations.RunPython(copy, refuse_populated_reverse)]
