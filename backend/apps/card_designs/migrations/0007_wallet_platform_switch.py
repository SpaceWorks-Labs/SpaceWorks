"""Per-space switch for the platform wallet-pass certificates (decisions 240, 281).

Default True: existing rows (and spaces with no row) keep today's behaviour, where the platform
fallback already applies.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("card_designs", "0006_wallet_credentials")]

    operations = [
        migrations.AddField(model_name="makerspacewalletcredentials", name="use_platform_credentials",
                            field=models.BooleanField(default=True)),
    ]
