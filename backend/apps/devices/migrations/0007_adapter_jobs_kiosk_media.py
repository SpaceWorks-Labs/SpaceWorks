"""Device Adapter API v1, part 3: per-binding safety config and opt-in watch recording."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("devices", "0006_device_adapter_api")]

    operations = [
        migrations.AddField(model_name="adapterbinding", name="config",
                            field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="adapterwatch", name="record", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="adapterwatch", name="recording_key",
                            field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name="adapterwatch", name="recording_expires_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="adapterwatch", name="recording_purged_at",
                            field=models.DateTimeField(blank=True, null=True)),
    ]
