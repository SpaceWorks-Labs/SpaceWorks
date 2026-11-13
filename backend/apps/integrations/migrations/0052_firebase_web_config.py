from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0051_plain_admin_names")]
    operations = [migrations.AddField(model_name="platformpushsettings", name="firebase_web_config",
                                      field=models.JSONField(blank=True, default=dict))]
