from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0034_staff_invitation_account")]
    operations = [
        migrations.AddField("staffinvitation", "role_snapshot", models.JSONField(default=list)),
        migrations.AddField("staffinvitation", "machine_scope_snapshot", models.JSONField(default=list)),
        migrations.AddField("staffinvitation", "credential_generation", models.PositiveIntegerField(default=0)),
    ]
