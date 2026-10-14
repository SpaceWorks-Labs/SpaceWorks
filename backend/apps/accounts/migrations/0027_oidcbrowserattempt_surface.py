from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0026_mfa_staff_invitations")]

    operations = [
        migrations.AddField(
            model_name="oidcbrowserattempt",
            name="surface",
            field=models.CharField(
                choices=[("member", "Member"), ("staff", "Staff")],
                default="member", max_length=16,
            ),
        ),
    ]
