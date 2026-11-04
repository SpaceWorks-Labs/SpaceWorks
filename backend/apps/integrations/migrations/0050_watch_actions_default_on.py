"""Lane L19: `mobile.watch_actions` is default-ON (#128 C-27).

`enabled_features` is stored per makerspace, so a default reaches new spaces only. This
backfills the switch onto existing spaces that have native push on (`mobile.push`); a space
that switched push off keeps watch actions off too, so turning push back on does not bring
action buttons it never had. Touches only rows lacking the key; the reverse removes it.
"""

from django.db import migrations

KEY = "mobile.watch_actions"


def enable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if "mobile.push" in features and KEY not in features:
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
        ("integrations", "0049_organization_email_sender"),
        ("makerspaces", "0118_security_policy"),
    ]

    operations = [migrations.RunPython(enable, disable)]
