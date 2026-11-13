from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("analytics", "0001_initial")]

    operations = [
        migrations.AddField(model_name="analyticsconnection", name="telemetry_config",
                            field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="platformanalyticsconnection", name="telemetry_config",
                            field=models.JSONField(blank=True, default=dict)),
    ]
