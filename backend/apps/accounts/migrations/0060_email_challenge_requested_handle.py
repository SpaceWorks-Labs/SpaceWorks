"""The username a new sign-up chose, claimed when the email is confirmed (SECURITY-REVIEW M14)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0059_staff_invitation_machine_ids")]

    operations = [
        migrations.AddField(
            "emailverificationchallenge", "requested_handle",
            models.CharField(blank=True, default="", max_length=30),
        ),
    ]
