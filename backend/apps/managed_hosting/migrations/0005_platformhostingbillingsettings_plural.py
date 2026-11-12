from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("managed_hosting", "0004_space_hosting_type")]

    operations = [
        migrations.AlterModelOptions(
            name="platformhostingbillingsettings",
            options={"verbose_name_plural": "platform hosting billing settings"},
        ),
    ]
