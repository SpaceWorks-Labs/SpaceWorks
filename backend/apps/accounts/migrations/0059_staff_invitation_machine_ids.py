from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0058_oidc_attempt_next_path")]

    operations = [
        migrations.AddField("staffinvitation", "machine_ids_snapshot", models.JSONField(default=list)),
    ]
