"""Parity O-B6 (decision 295): a space is a makerspace or an organization workspace."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0147_membershipplan_sac_code")]

    operations = [
        migrations.AddField(
            model_name="makerspace",
            name="kind",
            field=models.CharField(
                choices=[("makerspace", "Makerspace"), ("organization", "Organization")],
                default="makerspace", max_length=16),
        ),
    ]
