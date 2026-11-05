"""Lane L20: `platform.help_centre` is default-ON (#69, #128 C-31).

`enabled_features` is stored per makerspace, so a default reaches new spaces only. This
backfills the switch onto every existing space; it is a new key, so no space can have
turned it off yet. Touches only rows lacking the key; the reverse removes it. The help
centre stores nothing, so either direction loses no data.
"""

from django.db import migrations

KEY = "platform.help_centre"


def enable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if KEY not in features:
            Makerspace.objects.filter(pk=space.pk).update(enabled_features=[*features, KEY])


def disable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if KEY in features:
            Makerspace.objects.filter(pk=space.pk).update(
                enabled_features=[key for key in features if key != KEY])


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0122_technician_role_seed"),
    ]

    operations = [migrations.RunPython(enable, disable)]
