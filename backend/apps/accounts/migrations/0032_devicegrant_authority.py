from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0031_platformloginmethods_provider_switches")]

    operations = [
        migrations.AddField(
            model_name="devicegrant",
            name="authority",
            field=models.CharField(
                choices=[("member", "Member"), ("staff", "Staff")],
                default="member",
                max_length=16,
            ),
        ),
    ]
