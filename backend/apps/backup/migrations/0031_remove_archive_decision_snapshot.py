"""P1b: drop the request-time superadmin-access snapshot from BackupArchive.

Kept apart from 0030 so that, on reverse, rows are marked legacy in THIS
transaction and 0030's reverse re-adds the snapshot constraint in its own
(a RunPython and an AddConstraint on one table must not share a migration).
"""

from django.db import migrations


def mark_makerspace_archives_legacy(apps, schema_editor):
    BackupArchive = apps.get_model("backup", "BackupArchive")
    BackupArchive.objects.using(schema_editor.connection.alias).filter(
        scope="makerspace", superadmin_access_at_decision__isnull=True
    ).update(legacy_pre_decision_snapshot=True)


class Migration(migrations.Migration):
    dependencies = [("backup", "0030_remove_archive_custody")]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, mark_makerspace_archives_legacy),
        migrations.RemoveField(model_name="backuparchive", name="superadmin_access_at_decision"),
        migrations.RemoveField(model_name="backuparchive", name="legacy_pre_decision_snapshot"),
    ]
