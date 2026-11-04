"""Notices added by lane L6 (paid ticketing v2): one source module, registered in the catalogue.

Account notices (envelopes, the buyer's chosen channels) for an order: confirmation,
payment reminder, abandoned checkout, a type-change result and a cancelled pass
occurrence (with the due opened). The live check re-reads the order: it must still
exist, belong to the recipient and live in a servable space with events on.

People who may have no account yet -- an attendee invited to claim a seat, a ticket
transfer recipient -- get a direct email that names nobody else's details and carries
only their own single-use link (`orders_attendees.send_invite`, `transfers.send_offer`).
"""

from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit

SOURCE = "events.order"
EVENTS = ("order_confirmed", "order_payment_reminder", "order_abandoned", "ticket_type_changed",
          "pass_occurrence_cancelled")
DIRECT_EVENTS = ("ticket_claim_invite", "ticket_transfer_received")


def _copy(order, event_name, extra):
    title = order.series.title if order.series_id else order.event.title
    amount = f"{order.currency.upper()} {order.total}"
    if event_name == "order_confirmed":
        return (f"Your order for {title} is confirmed",
                f"Thank you. Your order #{order.pk} for {title} ({amount}) is confirmed. Places for other people "
                "are held until each person signs in and claims theirs; you can see who has claimed in My orders.")
    if event_name == "order_payment_reminder":
        return (f"Payment due for {title}", f"Your order #{order.pk} for {title} ({amount}) is waiting for payment.")
    if event_name == "order_abandoned":
        return (f"Your seats for {title} were released",
                f"The checkout for order #{order.pk} expired before payment, so its seats went back on sale. "
                "You can order again while places last.")
    if event_name == "ticket_type_changed":
        return (f"Your ticket for {title} changed", f"Your ticket type change for {title} is done.")
    if event_name == "pass_occurrence_cancelled":
        event = extra.get("event")
        when = timezone.localtime(event.starts_at).strftime("%d %b %Y") if event else "one date"
        due = extra.get("due")
        tail = (f" A refund of {order.currency.upper()} {due.amount} is waiting for staff approval." if due else "")
        return (f"An occurrence of {title} was cancelled",
                f"The {when} session of {title} was cancelled. Your pass still covers the other sessions.{tail}")
    return (f"Update on your order for {title}", f"There is an update on your order #{order.pk}.")


def order_notice(order, event_name, **extra):
    from apps.integrations.recipients_owners import eligible_owner
    if event_name not in EVENTS or not eligible_owner(order.makerspace, order.buyer_id):
        return None
    subject, text = _copy(order, event_name, extra)
    revision = str(extra.get("revision") or (getattr(extra.get("event"), "pk", None) or order.status))[:64]
    return emit(makerspace=order.makerspace, recipient=order.buyer, feature="events", stream="events",
                event=event_name, audience="requester", dedup_key=f"ev:order:{order.pk}:{event_name}:{revision}",
                source_kind=SOURCE, source_id=str(order.pk), revision=revision, subject=order,
                context={"order_id": order.pk, "notice": event_name},
                rendered={"subject": subject, "text": text, "html": "",
                          "link": local_link(order.makerspace, "member", f"orders/{order.pk}")})


def order_eligible(envelope):
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from .models import EventOrder
    order = EventOrder.objects.select_related("makerspace").filter(pk=envelope.context.get("order_id")).first()
    return bool(order and str(order.pk) == str(envelope.source_id) and order.buyer_id == envelope.recipient_id
                and order.makerspace_id == envelope.makerspace_id and envelope.audience == "requester"
                and is_servable(order.makerspace) and module_enabled(order.makerspace, "events"))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(order_eligible))
