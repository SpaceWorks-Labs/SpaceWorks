"""P1b (owner decision #111 Q2): retire the `backup` module key.

Backup and restore are platform duties now; Space Managers keep a read-only
"Last backup" line. Strip the key from every makerspace so the registry never
sees an unknown module. Reverse is a no-op: the key no longer exists.
"""

from django.db import migrations

MODULE_KEY = "backup"


def strip_backup_module(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for makerspace in Makerspace.objects.filter(enabled_modules__contains=[MODULE_KEY]):
        makerspace.enabled_modules = [
            key for key in makerspace.enabled_modules if key != MODULE_KEY
        ]
        makerspace.save(update_fields=["enabled_modules"])


class Migration(migrations.Migration):
    dependencies = [("backup", "0032_remove_lane_e_restore_state")]

    operations = [migrations.RunPython(strip_backup_module, migrations.RunPython.noop)]
