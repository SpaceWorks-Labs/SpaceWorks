"""#135 Q-S18 follow-up: shop variants offered on one of the space's event pages."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0069_l21b_guards_and_options"),
        ("makerspaces", "0126_shop_manager_role_seed"),
        ("shop", "0002_shop_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopEventOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shop_offers",
                                            to="events.event")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_offers",
                                              to="shop.shopvariant")),
            ],
            options={
                "ordering": ["event_id", "sort_order", "pk"],
                "constraints": [models.UniqueConstraint(fields=("event", "variant"), name="shop_event_offer_unique")],
            },
        ),
    ]
