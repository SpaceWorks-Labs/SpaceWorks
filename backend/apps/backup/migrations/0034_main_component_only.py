"""P1b (owner decision #110): a deployment archive has one platform-readable component.

Protocol v2 removed sovereign slices, so the artifact ledger's `slice` component
kind can never be written again. The check constraint now admits only the main
component with no tenant snapshot.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("backup", "0033_retire_backup_module")]

    operations = [
        migrations.RemoveConstraint(
            model_name="backupartifactcomponent",
            name="backup_component_kind_matches_tenant",
        ),
        migrations.AlterField(
            model_name="backupartifactcomponent",
            name="kind",
            field=models.CharField(choices=[("main", "Readable main")], max_length=8),
        ),
        migrations.AddConstraint(
            model_name="backupartifactcomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(kind="main", makerspace_id_snapshot__isnull=True),
                name="backup_component_main_only",
            ),
        ),
    ]
