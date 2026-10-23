from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0016_merge_analytics_watch")]
    operations = [
        migrations.AddField(
            model_name="inventoryproduct", name="is_consumable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="inventoryproduct",
            constraint=models.CheckConstraint(
                condition=models.Q(is_consumable=False) | models.Q(tracking_mode="quantity"),
                name="consumable_quantity_tracked",
            ),
        ),
    ]
