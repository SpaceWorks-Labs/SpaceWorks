"""Parity O-B3: a membership plan's own SAC code (blank = the space-wide one)."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0146_member_units")]

    operations = [
        migrations.AddField(
            model_name="membershipplan",
            name="sac_code",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
    ]
