"""Restore the built-in CNC Router's name.

0017 re-saved the built-in packs with ``slug.replace("_", " ").title()``, which turned
0002's "CNC Router" into "Cnc Router" on every install. Only the untouched generated name
is corrected, so a deployment that renamed the type keeps its own name.
"""

from django.db import migrations


def forward(apps, schema_editor):
    MachineType = apps.get_model("machines", "MachineType")
    MachineType.objects.filter(makerspace__isnull=True, slug="cnc_router", name="Cnc Router").update(name="CNC Router")


class Migration(migrations.Migration):
    dependencies = [("machines", "0033_plain_admin_names")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
