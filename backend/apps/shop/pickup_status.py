"""Read-only pickup projection using retained order/event records."""

from django.utils import timezone

from apps.makerspaces.platform import module_enabled

from .models import ShopOrder


def pickup_event_title(order) -> str:
    event = order.pickup_event
    return event.title if event is not None and event.makerspace_id == order.makerspace_id else ""


def pickup_requires_staff_confirmation(order) -> bool:
    if order.pickup_at != ShopOrder.Pickup.EVENT or order.status not in (
        *ShopOrder.OPEN_STATUSES, *ShopOrder.PAID_STATUSES,
    ):
        return False
    event = order.pickup_event
    return (
        event is None
        or event.makerspace_id != order.makerspace_id
        or not module_enabled(order.makerspace, "events")
        or event.status != event.Status.PUBLISHED
        or event.ends_at <= timezone.now()
    )
