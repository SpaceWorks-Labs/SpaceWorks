"""Release 2 L18: the booking and event calendar feeds get switches, on for existing spaces.

Both feeds existed before they had a switch, so every existing space keeps them exactly as
they were (#95: adding a switch never takes a feature away). New spaces get them from the
capability defaults. A Space Manager can turn either off afterwards; the rows are kept.
"""
from django.db import migrations

FEATURES = ("bookings.calendar_feed", "events.calendar_feed")


def enable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    alias = schema_editor.connection.alias
    for space in Makerspace.objects.using(alias).only("pk", "enabled_features").iterator():
        missing = [key for key in FEATURES if key not in (space.enabled_features or [])]
        if missing:
            space.enabled_features = [*(space.enabled_features or []), *missing]
            space.save(using=alias, update_fields=["enabled_features"])


def disable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    alias = schema_editor.connection.alias
    for space in Makerspace.objects.using(alias).only("pk", "enabled_features").iterator():
        kept = [key for key in (space.enabled_features or []) if key not in FEATURES]
        if kept != list(space.enabled_features or []):
            space.enabled_features = kept
            space.save(using=alias, update_fields=["enabled_features"])


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0119_l3_member_cards")]
    operations = [migrations.RunPython(enable, disable)]
