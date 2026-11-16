"""Shop merch offered at one of the space's events (#135 Q-S18 follow-up).

Event add-ons and shop merch stay separate (Q-S18): this row only says "show this shop
variant on that event's page". Buying it is an ordinary shop order with event pickup
(`shop.event_pickup`) -- a Shop-owned order and charge, never part of a registration.
The list is the Shop's; it references the event and shows only with Shop and Events on.
"""

from django.db import models


class ShopEventOffer(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="shop_offers")
    variant = models.ForeignKey("shop.ShopVariant", on_delete=models.CASCADE, related_name="event_offers")
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_id", "sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["event", "variant"], name="shop_event_offer_unique"),
        ]
