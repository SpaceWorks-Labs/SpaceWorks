"""A presence session names the account-level project (decision 304); the legacy FK stays for old rows."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("presence", "0004_display_screen"),
        ("makerspaces", "0153_account_profile_merge"),
    ]

    operations = [
        migrations.AddField(
            model_name="presencesession",
            name="account_project",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="+", to="makerspaces.accountproject"),
        ),
    ]
