"""Reconcile module state and preserve explicitly enabled v2 WhatsApp installs.

The module value is a JSON list, not a scalar field with Django ``choices``.
The live module registry validates the union (including presence, SMS and
WhatsApp). Freeze the field's actual declaration here rather than attaching
scalar choices that would reject every list during model validation.
"""

import apps.makerspaces.models
from django.db import migrations, models


def preserve_enabled_whatsapp(apps, schema_editor):
    alias = schema_editor.connection.alias
    Configuration = apps.get_model("integrations", "ChannelConfiguration")
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    # Only T's already-enabled installations retain their prior module access.
    # O settings, disabled configurations and new tenants remain default-off.
    # This never changes credentials, endpoint proofs, personal opt-outs or
    # platform switches; the separate messaging cutover still fences sending.
    ids = Configuration.objects.using(alias).filter(
        channel="whatsapp", enabled=True,
    ).values_list("makerspace_id", flat=True)
    rows = Makerspace.objects.using(alias)
    for space in rows.filter(pk__in=ids).only("pk", "enabled_modules").iterator(chunk_size=500):
        modules = list(space.enabled_modules or [])
        if "whatsapp" not in modules:
            rows.filter(pk=space.pk).update(enabled_modules=[*modules, "whatsapp"])


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0096_enable_existing_presence"),
        ("integrations", "0040_merge_mobile_notifications"),
    ]
    operations = [
        migrations.AlterField(
            model_name="makerspace", name="enabled_modules",
            field=models.JSONField(blank=True, default=apps.makerspaces.models.default_enabled_modules),
        ),
        # Removing a key on reverse could undo a later explicit operator install.
        migrations.RunPython(preserve_enabled_whatsapp, migrations.RunPython.noop),
    ]
