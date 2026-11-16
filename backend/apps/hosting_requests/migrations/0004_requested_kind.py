"""Parity O-B6 (decision 295): a request asks for a makerspace or an organization workspace."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hosting_requests", "0003_expected_members")]

    operations = [
        migrations.AddField(
            model_name="hostingrequest",
            name="requested_kind",
            field=models.CharField(
                choices=[("makerspace", "Makerspace"), ("organization", "Organization workspace")],
                default="makerspace", max_length=16),
        ),
    ]
