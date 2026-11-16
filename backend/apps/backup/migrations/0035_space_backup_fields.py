"""Per-space backup (owner decisions #110d, #111 Q3/Q4).

BackupArchive records its payload format and what triggered it; nightly per-space
archives rotate like the nightly run's.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("backup", "0034_main_component_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="backuparchive",
            name="format",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="backuparchive",
            name="trigger",
            field=models.CharField(
                choices=[("on_demand", "Back up now"), ("nightly", "Nightly"), ("safety", "Before a restore")],
                default="on_demand", max_length=16,
            ),
        ),
    ]
