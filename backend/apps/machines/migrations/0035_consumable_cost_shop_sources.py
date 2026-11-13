"""Shop sales of a linked inventory consumable record their cost (decision 216 item 11).

Choices only: no column, constraint or trigger changes. `shop_sale` and `shop_return` key on
`shop.ShopStockMovement`; the existing (makerspace, source_kind, source_id) unique constraint
makes each exactly-once.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("machines", "0034_builtin_cnc_router_name")]
    operations = [
        migrations.AlterField(
            model_name="consumablecostrecord",
            name="source_kind",
            field=models.CharField(choices=[
                ("pooled_service", "pooled_service"), ("manual_adjustment", "manual_adjustment"),
                ("non_pool_consumption", "non_pool_consumption"), ("shop_sale", "shop_sale"),
                ("shop_return", "shop_return"),
            ], max_length=32),
        ),
    ]
