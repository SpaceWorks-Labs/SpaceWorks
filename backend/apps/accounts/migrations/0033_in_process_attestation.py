from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0032_devicegrant_authority")]

    operations = [
        migrations.AddField(
            model_name="devicegrant", name="attestation_key_id",
            field=models.CharField(max_length=512, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="devicegrant", name="attestation_public_key",
            field=models.TextField(null=True, blank=True),
        ),
        migrations.CreateModel(
            name="PlatformAttestationSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("play_integrity_service_account", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
