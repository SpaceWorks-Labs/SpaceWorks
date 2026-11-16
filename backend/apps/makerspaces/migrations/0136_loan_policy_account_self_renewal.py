"""Decision 221(a): Space Manager switch for account-only borrower self-renewal (default off)."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0135_membership_plan_included_hours")]
    operations = [
        migrations.AddField(
            model_name="makerspaceloanpolicy", name="account_self_renewal",
            field=models.BooleanField(default=False),
        ),
    ]
