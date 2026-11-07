from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0132_makerspace_default_locale")]
    operations = [migrations.AddField(
        model_name="makerspace", name="public_stats_config", field=models.JSONField(default=dict, blank=True),
    )]
