from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0041_reconcile_native_account_context")]

    operations = [
        migrations.AddField(
            model_name="platformattestationsettings", name="app_display_name",
            field=models.CharField(default="SpaceWorks", max_length=100),
        ),
        migrations.AddConstraint(
            model_name="nativeappregistration",
            constraint=models.UniqueConstraint(
                fields=("platform", "environment"),
                condition=models.Q(makerspace__isnull=True, status="approved"),
                name="uniq_approved_deployment_app",
                violation_error_message="Only one approved deployment app per platform and environment is allowed. Rotate signers on the existing registration, or revoke it before approving its replacement.",
            ),
        ),
    ]
