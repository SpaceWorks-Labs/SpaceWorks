"""Keep existing tenants' check-in and self-checkout presence requirement on upgrade."""
from django.db import migrations


def enable_existing_presence(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    rows = Makerspace.objects.using(schema_editor.connection.alias)
    for space in rows.all().iterator():
        modules = space.enabled_modules or []
        if "presence" not in modules:
            rows.filter(pk=space.pk).update(enabled_modules=[*modules, "presence"])


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0095_booking_requester_notifications_default_on")]
    # No reverse removal: that could undo an operator's subsequent explicit install.
    operations = [migrations.RunPython(enable_existing_presence, migrations.RunPython.noop)]
