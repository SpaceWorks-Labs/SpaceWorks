"""Placing an order (release 2 L6, G27/G28): quote -> hold -> one Payment -> checkout.

Inside the event write boundary (event, then makerspace locks) the quote is rebuilt with
the promo and access-code rows locked, checked against the digest the buyer was shown
(409 `price_changed`), and frozen on the order. A priced order raises ONE `Payment`
(subject `event_order`) through the record-first ledger seam; the online checkout is
scheduled after commit and may fail without losing the debt. With `events.seat_holds` on
the seats are held for `HOLD_MINUTES`, the shortest hosted-checkout session a provider
allows. A free order settles at once.

Orders run on events open to members or to any account, without approval. Approval and
invitation events keep the single-registration flow, whose charge is raised on approval; with
`events.accepted_addons` on, a CONFIRMED registration there may order add-ons alone (hack-money G9).
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.audit.services import record

from .models import EventCheckoutHold, EventOrder, EventOrderLine
from .orders_errors import OrderRefused
from .services_write_boundary import event_write

logger = logging.getLogger(__name__)
HOLD_MINUTES = 30
ORDER_AUDIENCES = ("members", "accounts")


def addons_only(event, member, request):
    """Hack-money G9 (`events.accepted_addons`): on an event that reviews registrations, a person
    already CONFIRMED there may order add-ons alone (a T-shirt, meals, a hardware kit). No seat is
    sold, so the approval and capacity rules that keep seat orders off such events are untouched."""
    from apps.makerspaces.platform import feature_enabled
    if request is None or request.get("tickets") or not request.get("addons"):
        return False
    if not event.registration_requires_approval or not feature_enabled(event.makerspace, "events.accepted_addons"):
        return False
    return member is not None and event.registrations.filter(member=member, status__in=("registered", "attended")).exists()


def require_orderable(event, member, request=None):
    from .capacity import registration_is_open
    from .registration_access import require_registration_access
    if addons_only(event, member, request):
        if event.ends_at <= timezone.now():
            raise OrderRefused("sold_out", "This event has ended.")
        return
    if event.registration_audience not in ORDER_AUDIENCES or event.registration_requires_approval:
        raise OrderRefused("order_not_payable", "This event takes single registrations only.")
    if not registration_is_open(event, timezone.now()):
        raise OrderRefused("sold_out", "Registration for this event is closed.")
    require_registration_access(event, member)


def _payment(order, actor):
    from apps.payments.availability import charge_tracking_enabled
    from apps.payments.models import Payment
    from apps.payments.services import create_payment
    if not charge_tracking_enabled(order.makerspace, "events"):
        raise OrderRefused("order_not_payable", "This space is not taking payments for events.")
    from apps.managed_hosting.space_quotas import require_payment_capacity
    require_payment_capacity(order.makerspace, order.total, order.currency)
    first = order.event or order.seats.select_related("event").order_by("event__starts_at").first().event
    return create_payment(
        makerspace=order.makerspace, subject_type=Payment.SubjectType.EVENT_ORDER, subject_id=order.pk,
        member=order.buyer, amount=order.total, currency=order.currency, created_by=actor,
        subject_label=(order.series.title if order.series_id else order.event.title), due_at=first.starts_at,
        pricing_snapshot=order.pricing_snapshot)


def _schedule_checkout(payment):
    from apps.payments.availability import online_payments_enabled
    if not online_payments_enabled(payment.makerspace, "events"):
        return
    from apps.payments.services import create_checkout
    try:
        create_checkout(payment)
    except Exception:
        logger.error("Event order checkout scheduling failed", extra={"payment_id": payment.pk})


def _lines(order, priced):
    for (ticket, quantity, unit), quote_line in zip(priced.tickets, priced.quote.lines):
        EventOrderLine.objects.create(order=order, kind=EventOrderLine.Kind.TICKET, ticket_type=ticket,
                                      label=ticket.name, quantity=quantity, seats_per_unit=ticket.seats_per_ticket,
                                      unit_amount=unit, discount_amount=quote_line.discount, line_total=quote_line.net)
    offset = len(priced.tickets)
    for (addon, variant, quantity), quote_line in zip(priced.addons, priced.quote.lines[offset:]):
        EventOrderLine.objects.create(order=order, kind=EventOrderLine.Kind.ADDON, addon=addon, variant=variant,
                                      label=quote_line.detail.get("label", addon.name), quantity=quantity,
                                      unit_amount=quote_line.unit_amount, discount_amount=quote_line.discount,
                                      line_total=quote_line.net)


@event_write
def place_order(event, *, member, actor, request, digest=None):
    """Create a pending (or, when free, paid) order for `member`. Returns `(order, payment)`."""
    from apps.makerspaces.guards import require_module_locked
    from apps.makerspaces.platform import feature_enabled
    from apps.payments.pricing import verify_digest
    from .orders_codes import spend
    from .orders_quote import build_quote
    event.makerspace = require_module_locked(event.makerspace, "events")
    require_orderable(event, member, request)
    only_addons = addons_only(event, member, request)
    priced = build_quote(event, member, request, lock=True, addons_only=only_addons)
    verify_digest(priced.quote, digest)
    attendees = [str(email).strip().lower() for email in request.get("attendees") or () if str(email).strip()]
    if not only_addons:  # decision 284: a ticket order is the START of registrations (add-on orders sell no seat)
        from apps.managed_hosting.extra_quotas import check_extra_quota
        check_extra_quota(event.makerspace, "event_registrations_monthly", adding=priced.seats)
    order = EventOrder.objects.create(
        makerspace=event.makerspace, event=event, buyer=member, currency=priced.quote.currency,
        subtotal=priced.quote.subtotal, discount_total=priced.quote.discount_total,
        fee_total=sum((line.net for line in priced.quote.lines if line.component == "booking_fee"), 0),
        total=priced.quote.total, digest=priced.quote.digest, promo_code=priced.promo,
        pricing_snapshot=priced.quote.to_snapshot(buyer_attends=bool(request.get("buyer_attends", True)),
                                                  attendees=len(attendees)))
    _lines(order, priced)
    spend(priced.promo, priced.promo_uses)
    for promo in priced.access_promos:
        spend(promo, 1)
    from .orders_attendees import create_seats
    if not only_addons:  # G9: an add-on-only order sells no seat
        create_seats(order, attendees=attendees, buyer_attends=bool(request.get("buyer_attends", True)))
    record(actor, "event.order_created", makerspace=event.makerspace, target=order,
           meta={"order_id": order.pk, "event_id": event.pk, "seats": priced.seats, "total": str(order.total),
                 "promo_id": getattr(priced.promo, "pk", None)})
    if order.total <= 0:
        from .orders_settlement import settle_locked
        settle_locked(order, actor=actor)
        return order, None
    payment = _payment(order, actor)
    if priced.seats and feature_enabled(event.makerspace, "events.seat_holds"):
        EventCheckoutHold.objects.create(makerspace=event.makerspace, order=order, event=event, seats=priced.seats,
                                         expires_at=timezone.now() + timedelta(minutes=HOLD_MINUTES))
    _schedule_checkout(payment)
    return order, payment
