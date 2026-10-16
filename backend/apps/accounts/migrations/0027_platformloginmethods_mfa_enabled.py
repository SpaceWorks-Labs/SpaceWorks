from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0026_mfa_staff_invitations")]

    operations = [
        migrations.AddField(
            model_name="platformloginmethods",
            name="mfa_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Two-step sign-in with an authenticator. Turning this off also overrides "
                    "staff-MFA-required makerspaces; enrolled authenticators are retained."
                ),
            ),
        ),
    ]
