from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("managed_hosting", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformhostingbillingsettings",
            name="hosting_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
