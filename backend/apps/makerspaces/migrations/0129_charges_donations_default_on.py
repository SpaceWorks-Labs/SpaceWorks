"""#184 G10: `charges.donations` is default-ON and backfilled onto every existing space.

Gifts, pledge periods and sponsor charges were always recorded wherever `finance.donations` /
`finance.sponsors` were on; the new key only lets a space switch that recording off. Without
this backfill every existing space would read it as OFF and start refusing gifts the day this
ships. It is a new key, so no space can have turned it off yet. Touches only rows lacking the
key; the reverse removes it. The key stores nothing, so neither direction loses data.
"""

from django.db import migrations

KEY = "charges.donations"


def enable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if KEY not in features:
            Makerspace.objects.filter(pk=space.pk).update(enabled_features=sorted({*features, KEY}))


def disable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if KEY in features:
            Makerspace.objects.filter(pk=space.pk).update(
                enabled_features=[key for key in features if key != KEY])


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0128_member_card_email_format"),
    ]

    operations = [migrations.RunPython(enable, disable)]
