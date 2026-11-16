"""Parity E-B2 (decision 294): the three badge switches are default-ON and backfilled where event ID cards are on.

`events.badge_designer`, `events.badge_desk_print` and `events.role_badges` are new keys, so no space has turned
one off. A space that already runs event ID cards (`events.id_cards` stored in `enabled_features`) gets all three,
so the structured designer, desk printing and role badges appear for it the day this ships. Spaces without event
ID cards are left alone (the keys require that parent anyway). The reverse removes the three keys; they store
nothing, so neither direction loses data.
"""

from django.db import migrations

PARENT = "events.id_cards"
KEYS = ("events.badge_designer", "events.badge_desk_print", "events.role_badges")


def enable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if PARENT in features and not set(KEYS) <= set(features):
            Makerspace.objects.filter(pk=space.pk).update(enabled_features=sorted({*features, *KEYS}))


def disable(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.only("pk", "enabled_features").iterator():
        features = list(space.enabled_features or [])
        if any(key in features for key in KEYS):
            Makerspace.objects.filter(pk=space.pk).update(
                enabled_features=[key for key in features if key not in KEYS])


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0150_space_email_sender_verification"),
    ]

    operations = [migrations.RunPython(enable, disable)]
