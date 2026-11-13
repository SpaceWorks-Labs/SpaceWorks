"""Typed shop refusals (release 2 L22): `{detail, code}` bodies with stable codes.

The codes the brief names: `out_of_stock`, `hold_expired`, `price_changed`, `per_order_limit`,
`member_only`, `shop_closed`, `pickup_code_invalid`, `cash_session_closed`, plus a few shape
errors (`feature_off`, `guest_identity_required`, `order_not_cancellable`, ...).
"""

from django.utils.translation import gettext_lazy, gettext
from rest_framework.exceptions import APIException

from apps.payments.pricing.errors import ChargesOff

STATUS = {
    "out_of_stock": 409, "hold_expired": 409, "price_changed": 409, "per_order_limit": 400,
    "member_only": 403, "shop_closed": 404, "feature_off": 404, "pickup_code_invalid": 404,
    "cash_session_closed": 409, "cash_session_open": 409, "cash_session_check": 409,
    "guest_identity_required": 400, "order_empty": 400, "item_unavailable": 409,
    "order_not_cancellable": 409, "order_not_collectable": 409, "order_not_payable": 409,
    "return_window_closed": 409, "return_exceeds_sold": 400, "pickup_event_invalid": 400,
    "pickup_interrupted": 409, "idempotency_key_reused": 409, "charges_off": 409, "variant_invalid": 400, "link_invalid": 400, "not_found": 404,
}


class ShopRefused(APIException):
    status_code = 409
    default_code = "shop_refused"

    def __init__(self, code, detail, **extra):
        self.status_code = STATUS.get(code, 409)
        super().__init__({"detail": detail, "code": code, **extra})
        self.detail = {"detail": detail, "code": code, **extra}
        self.code = code


class ShopQuoteChargesOff(ChargesOff):
    message = gettext_lazy("This shop is not taking orders right now.")


def out_of_stock(error, labels=None):
    """An availability `OutOfStock` as a typed 409 naming the variant and what is left."""
    variant_id = getattr(error, "variant_id", None)
    label = (labels or {}).get(variant_id, "An item")
    return ShopRefused("out_of_stock", gettext("%(label)s does not have enough stock left.") % {"label": label},
                       variant_id=variant_id, available=getattr(error, "available", 0))
