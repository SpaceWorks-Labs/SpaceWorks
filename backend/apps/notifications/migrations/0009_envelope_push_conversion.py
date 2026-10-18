"""CONVERT only after expansion, drained writers and M's history copy checkpoint."""
from django.db import migrations
from ._push_conversion_v1 import convert


def refuse_populated_reverse(registry, schema_editor):
    """Only a graph with no push history may be unapplied (fresh/test databases).

    Converted rows are never reverse-converted: that would restore queued send
    authority to canceled or held attempts. Populated installations keep refusing.
    """
    alias = schema_editor.connection.alias
    Push = registry.get_model("notifications", "MemberPushDelivery")
    Mapping = registry.get_model("integrations", "NotificationLegacyMapping")
    if (Push.objects.using(alias).exists()
            or Mapping.objects.using(alias).filter(legacy_model="MemberPushDelivery").exists()):
        raise RuntimeError("0009 push conversion is irreversible once push history exists")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("notifications", "0008_envelope_push_expansion")]
    operations = [migrations.RunPython(convert, refuse_populated_reverse)]
