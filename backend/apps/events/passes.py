"""Series passes (release 2 L6, G31): one order admits the buyer to every future occurrence.

A pass covers the occurrences that are published and still ahead when it is bought; it
needs a place in each of them. It is an order of kind `pass` on the series with one seat
per occurrence, each turned into the buyer's ordinary registration (no charge of its
own) once paid. When the space cancels one occurrence, each pass holder is owed the pass
type's `occurrence_refund_amount` -- the organiser's partial amount -- as a staff-approved
refund case (`orders_refunds.event_cancelled`). Skipping an occurrence owes nothing.
"""

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record

from .models import Event, EventCheckoutHold, EventOrder, EventOrderLine, EventOrderSeat, EventPassType
from .orders_errors import OrderRefused
from .services_write_boundary import event_write

PASS_FIELDS = ("name", "amount", "capacity", "occurrence_refund_amount", "sales_end_at", "is_active")


def _require_feature(series):
    from apps.makerspaces.platform import feature_enabled
    from rest_framework.exceptions import ValidationError
    if not feature_enabled(series.makerspace, "events.series_passes"):
        raise ValidationError({"detail": "This events feature is disabled."})


def passes_sold(pass_type):
    live = (Q(order__status=EventOrder.Status.PAID)
            | Q(order__status=EventOrder.Status.PENDING, order__hold__released_at__isnull=True,
                order__hold__expires_at__gt=timezone.now()))
    return EventOrderLine.objects.filter(live, pass_type=pass_type).aggregate(total=Sum("quantity"))["total"] or 0


def covered_occurrences(series):
    return list(Event.objects.filter(series=series, status=Event.Status.PUBLISHED,
                                     starts_at__gt=timezone.now()).order_by("starts_at", "pk"))


@transaction.atomic
def save_pass_type(series, *, actor, pass_type=None, **values):
    from apps.makerspaces.guards import require_module_locked
    from .models import EventSeries
    series = EventSeries.objects.select_for_update().select_related("makerspace").get(pk=series.pk)
    series.makerspace = require_module_locked(series.makerspace, "events")
    _require_feature(series)
    row = pass_type or EventPassType(makerspace=series.makerspace, series=series)
    if pass_type is not None and "amount" in values and values["amount"] != row.amount and row.order_lines.exists():
        from .ticketing_edit import ReferencedConflict
        raise ReferencedConflict("The price is fixed once passes were sold. Add a new pass type instead.",
                                 "pass_type_referenced")
    for key in PASS_FIELDS:
        if key in values:
            setattr(row, key, values[key])
    row.save()
    record(actor, "event.pass_type_saved", makerspace=series.makerspace, target=row,
           meta={"series_id": series.pk, "created": pass_type is None})
    return row


def _require_room(pass_type, occurrences, member):
    from .capacity import registration_spots_left
    from .registration_access import require_registration_access
    if pass_type.capacity and passes_sold(pass_type) >= pass_type.capacity:
        raise OrderRefused("sold_out", "This pass has sold out.")
    if not occurrences:
        raise OrderRefused("sold_out", "There are no upcoming occurrences to cover.")
    for event in occurrences:
        require_registration_access(event, member)
        left = registration_spots_left(event, None)
        if left is not None and left < 1:
            raise OrderRefused("sold_out", "One of the occurrences is full.", event_id=event.pk)
        if event.registrations.filter(member=member, status__in=("pending_approval", "registered",
                                                                 "waitlisted", "attended")).exists():
            raise OrderRefused("already_registered", "You already have a place at one of these occurrences.",
                               event_id=event.pk)


def pass_quote(series, pass_type):
    from apps.payments.pricing.quotes import Quote, line
    from apps.payments.pricing.rates import RateCard
    from .orders_quote import PASS
    currency = RateCard(series.makerspace, "events").currency
    item = line(PASS, currency=currency, quantity=1, unit_amount=pass_type.amount, rate_source="item",
                target={"type": "series", "id": series.pk, "label": series.title},
                detail={"pass_type_id": pass_type.pk, "label": pass_type.name})
    return Quote(domain="events", currency=currency, lines=(item,), mode="paid")


@event_write
def place_pass_order(series, *, member, actor, pass_type_id, digest=None):
    from datetime import timedelta
    from apps.makerspaces.platform import feature_enabled
    from apps.payments.pricing import verify_digest
    from .orders_checkout import HOLD_MINUTES, _payment, _schedule_checkout
    _require_feature(series)
    pass_type = EventPassType.objects.filter(pk=pass_type_id, series=series, is_active=True).first()
    if pass_type is None or (pass_type.sales_end_at and pass_type.sales_end_at <= timezone.now()):
        raise OrderRefused("sold_out", "That pass is not on sale.")
    occurrences = covered_occurrences(series)
    _require_room(pass_type, occurrences, member)
    quote = verify_digest(pass_quote(series, pass_type), digest)
    order = EventOrder.objects.create(makerspace=series.makerspace, series=series, buyer=member,
                                      kind=EventOrder.Kind.PASS, currency=quote.currency, subtotal=quote.subtotal,
                                      total=quote.total, digest=quote.digest,
                                      pricing_snapshot=quote.to_snapshot(occurrences=[e.pk for e in occurrences]))
    line = EventOrderLine.objects.create(order=order, kind=EventOrderLine.Kind.PASS, pass_type=pass_type,
                                         label=pass_type.name, quantity=1, seats_per_unit=1,
                                         unit_amount=pass_type.amount, line_total=quote.total)
    for event in occurrences:
        EventOrderSeat.objects.create(makerspace=series.makerspace, order=order, line=line, event=event,
                                      attendee_email=(member.email or "").strip().lower())
    record(actor, "event.pass_order_created", makerspace=series.makerspace, target=order,
           meta={"order_id": order.pk, "series_id": series.pk, "occurrences": len(occurrences)})
    if order.total <= 0:
        from .orders_settlement import settle_locked
        return settle_locked(order, actor=actor), None
    payment = _payment(order, actor)
    if feature_enabled(series.makerspace, "events.seat_holds"):
        EventCheckoutHold.objects.create(makerspace=series.makerspace, order=order, event=occurrences[0],
                                         seats=len(occurrences),
                                         expires_at=timezone.now() + timedelta(minutes=HOLD_MINUTES))
    _schedule_checkout(payment)
    return order, payment


@event_write
def settle_pass_order(series, *, actor, order_id):
    from .orders_settlement import settle_locked
    order = EventOrder.objects.select_for_update().filter(pk=order_id, series=series).first()
    return settle_locked(order, actor=actor) if order is not None else None
