from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0031_daily_digest_default")]
    operations = [
        migrations.AddField("emaillog", "source_kind", models.CharField(max_length=48, blank=True)),
        migrations.AddField("emaillog", "source_id", models.PositiveBigIntegerField(null=True, blank=True)),
        migrations.AddField("emaillog", "source_metadata", models.JSONField(default=dict, blank=True)),
    ]
