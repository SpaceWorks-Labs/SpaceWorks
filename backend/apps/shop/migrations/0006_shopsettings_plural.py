from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("shop", "0005_order_idempotency_key")]

    operations = [
        migrations.AlterModelOptions(name="shopsettings", options={"verbose_name_plural": "shop settings"}),
    ]
