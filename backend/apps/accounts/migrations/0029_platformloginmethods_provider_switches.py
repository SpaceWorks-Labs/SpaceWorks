from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0028_platformsocialauthsettings_github")]

    operations = [
        migrations.AddField(
            model_name="platformloginmethods", name=provider + "_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Chosen at install; change with manage.py set_login_methods.",
            ),
        )
        for provider in ("google", "apple", "github")
    ] + [
        migrations.AlterField(
            model_name="platformloginmethods", name="mfa_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Chosen at install; change with manage.py set_login_methods. Turning off overrides "
                    "staff-MFA-required makerspaces; enrolled authenticators are retained."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="platformloginmethods", name="social_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Sign-in through an identity provider — the built-in Google, Apple and GitHub "
                    "providers and every configured OIDC provider. They share one endpoint, so "
                    "they share one switch."
                ),
            ),
        ),
    ]
