from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0033_account_context_triggers")]
    operations = [
        migrations.AddField(
            model_name="staffinvitation",
            name="account",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE,
                null=True, blank=True, related_name="staff_invitations",
            ),
        ),
    ]
