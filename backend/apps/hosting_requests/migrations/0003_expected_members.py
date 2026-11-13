# Owner decision #185 item 5: the onboarding request records the expected size.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hosting_requests", "0002_changes_requested")]

    operations = [
        migrations.AddField(
            model_name="hostingrequest",
            name="expected_members",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
