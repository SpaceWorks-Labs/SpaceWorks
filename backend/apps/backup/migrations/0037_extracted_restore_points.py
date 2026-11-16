"""A per-space restore point can be extracted from a whole-platform backup (#144)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("backup", "0036_makerspace_restore_operation")]

    operations = [
        migrations.AlterField(
            model_name="backuparchive",
            name="trigger",
            field=models.CharField(
                choices=[("on_demand", "Back up now"), ("nightly", "Nightly"), ("safety", "Before a restore"),
                         ("extracted", "From a whole-platform backup")],
                default="on_demand", max_length=16,
            ),
        ),
    ]
