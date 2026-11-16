"""Decision 221b: products lendable only within an event context."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0020_equipment_use_receipt")]
    operations = [
        migrations.AddField(
            model_name="inventoryproduct", name="event_only",
            field=models.BooleanField(default=False),
        ),
    ]
