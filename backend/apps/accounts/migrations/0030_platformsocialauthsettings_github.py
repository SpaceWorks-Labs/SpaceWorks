from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0029_platformloginmethods_mfa_enabled")]

    operations = [
        migrations.AddField(
            model_name="platformsocialauthsettings",
            name="github_client_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="platformsocialauthsettings",
            name="github_client_secret",
            field=models.TextField(blank=True, default=""),
        ),
    ]
