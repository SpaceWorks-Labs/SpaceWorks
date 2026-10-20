"""Interface effects and easter eggs become on by default for existing spaces too.

No space could choose these before (they were deployment-only flags), so there is no
"explicitly turned off" marker to respect: every existing space gets both features.
A space can turn either off afterwards in its feature settings.
"""
from django.db import migrations

FEATURES = ("ui.delight", "ui.easter_eggs")


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
    dependencies = [("makerspaces", "0097_reimbursement_payout_action")]
    operations = [migrations.RunPython(enable, disable)]
