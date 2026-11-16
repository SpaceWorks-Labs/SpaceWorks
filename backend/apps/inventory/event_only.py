"""Event-only lending (decision 221b): products lendable only within an event context.

`InventoryProduct.event_only` is a plain flag read here and at the three ordinary lending
doors -- public request intake, self-checkout and direct handout -- which all refuse such a
product with `409 event_only_product`. The one door that admits it is the contextual
equipment proposal bound to an event registration (its event context is the proof);
a booking-only context is not an event and is refused. No stock is moved here.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import APIException

from apps.inventory.models import InventoryProduct


class EventOnlyProduct(APIException):
    status_code = 409
    default_code = "event_only_product"

    def __init__(self, names=()):
        super().__init__({"detail": gettext("This item can only be borrowed through an event."),
                          "code": self.default_code, "products": sorted(set(names))[:20]})


def refuse_event_only(products):
    """Raise `EventOnlyProduct` naming every event-only product among `products`."""
    names = [product.name for product in products if product.event_only]
    if names:
        raise EventOnlyProduct(names)


def refuse_event_only_ids(makerspace, product_ids):
    names = list(InventoryProduct.objects.filter(
        makerspace=makerspace, pk__in=list(product_ids), event_only=True).values_list("name", flat=True))
    if names:
        raise EventOnlyProduct(names)
