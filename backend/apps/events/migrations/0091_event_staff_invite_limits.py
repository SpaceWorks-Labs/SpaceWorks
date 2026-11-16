from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0090_event_equipment_221b")]
    operations = [
        migrations.AddField("eventstaffgrantinvite", "track_ids", models.JSONField(blank=True, default=list)),
        migrations.AddField("eventstaffgrantinvite", "valid_from", models.DateTimeField(blank=True, null=True)),
        migrations.AddField("eventstaffgrantinvite", "valid_until", models.DateTimeField(blank=True, null=True)),
    ]
