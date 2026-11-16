import math
from typing import Any

from apps.inventory.models import InventoryProduct, PublicAvailabilityMode


EVENT_ONLY_LABEL = "Lent at events only"


def _status_label(product: InventoryProduct) -> str:
    available = product.available_quantity
    total = product.total_quantity

    if available <= 0 or total <= 0:
        return "Unavailable"

    if available <= math.ceil(total * 0.2):
        return "Limited"

    return "Available"


def get_public_availability(product: InventoryProduct) -> dict[str, Any] | None:
    if product.public_availability_mode == PublicAvailabilityMode.HIDDEN:
        return None

    if getattr(product, "event_only", False):
        # Decision 221b: neutral label only -- no count, no stock status, and no request button.
        return {"mode": PublicAvailabilityMode.STATUS_ONLY.value, "label": EVENT_ONLY_LABEL}

    label = _status_label(product)

    if product.public_availability_mode == PublicAvailabilityMode.STATUS_ONLY:
        return {"mode": PublicAvailabilityMode.STATUS_ONLY.value, "label": label}

    if (
        product.public_availability_mode == PublicAvailabilityMode.EXACT_COUNT
        and product.show_public_count
    ):
        return {
            "mode": PublicAvailabilityMode.EXACT_COUNT.value,
            "count": product.available_quantity,
            "label": label,
        }

    return {"mode": PublicAvailabilityMode.STATUS_ONLY.value, "label": label}
