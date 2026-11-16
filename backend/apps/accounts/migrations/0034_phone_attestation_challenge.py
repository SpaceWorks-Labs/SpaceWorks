from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0033_in_process_attestation")]

    operations = [
        migrations.AddField(
            model_name="phoneverificationchallenge",
            name="attestation_challenge",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="phone_login_challenges",
                to="accounts.deviceattestationchallenge",
            ),
        ),
    ]
