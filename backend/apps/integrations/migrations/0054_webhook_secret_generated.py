"""Parity E-B8: a signed webhook's retiring secret and its grace window (rotation without dropping events)."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0053_platform_credential_switch")]

    operations = [
        migrations.AddField(model_name="notificationdestination", name="previous_signing_secret",
                            field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="notificationdestination", name="previous_secret_valid_until",
                            field=models.DateTimeField(blank=True, null=True)),
    ]
