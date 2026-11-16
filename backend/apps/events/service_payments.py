"""Record the ledger atomically; outbound checkout failures leave the debt intact."""

import logging

from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)


def registration_amount(registration):
    return registration.quoted_amount if registration.quoted_amount is not None else registration.event.payment_amount


def member_price(event, member, amount, ticket=None):
    """Lane L15 hook (A3): `(price, saving)` after the member's ONE best automatic discount.

    Applied BEFORE any promo code, which the registration quote then takes off the
    discounted price. Lane L6 owns the order quote after this; it keeps the same order.
    """
    from decimal import Decimal

    from apps.payments.pricing import quote

    from .orders_context import current_seat
    if current_seat() is not None and current_seat().event_id == event.pk:
        # Lane L6: the order's Payment holds this seat's money; the registration owes nothing.
        return Decimal("0"), Decimal("0")
    if member is None or not getattr(member, "is_authenticated", False) or Decimal(amount) <= 0:
        return Decimal(amount), Decimal("0")
    priced = quote(event.makerspace, "events", event, member=member, params={"ticket": ticket})
    if priced.discount is None or priced.subtotal != Decimal(amount):
        return Decimal(amount), Decimal("0")
    return priced.total, priced.discount_total


def registration_snapshot(registration):
    """The frozen quote for a registration charge: list price, discount, what is owed."""
    from decimal import Decimal

    from apps.payments.pricing.components import component
    from apps.payments.pricing.quotes import Quote, line

    owed = Decimal(registration_amount(registration))
    discount = Decimal(registration.discount_amount or 0)
    event = registration.event
    currency = MakerspacePaymentSettings.for_makerspace(event.makerspace).default_currency
    item = line(component("events", "per_registration"), currency=currency, quantity=1,
                unit_amount=owed + discount, rate_source="registration",
                target={"type": "event", "id": event.pk, "label": event.title},
                detail={"ticket_type_id": registration.ticket_type_id, "promo_code_id": registration.promo_code_id})
    from dataclasses import replace
    priced = Quote(domain="events", currency=currency, lines=(replace(item, discount=discount),), mode="paid")
    return priced.to_snapshot()

from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import MakerspacePaymentSettings, Payment
from apps.payments.refund_cancellation import cancel_or_hold
from apps.payments.services import create_checkout, create_payment


def create_for_registered_registration(registration, actor):
    event = registration.event
    member = registration.member
    # Hack-money G10: a confirmed place may also owe a refundable deposit, even at a free event.
    from apps.events.judging.deposits import raise_deposit
    raise_deposit(registration, actor)
    if (member is None or registration.is_crew or registration_amount(registration) <= 0
            or not charge_tracking_enabled(event.makerspace, "events")):
        return None  # a crew place (lane L21a) is never charged
    # A local ledger failure rolls back the registration/approval transaction. Only
    # the optional provider rail may fail safely after the debt has been recorded.
    payment = _get_or_create(registration, actor or member)
    try:
        if payment.status == Payment.Status.PENDING and online_payments_enabled(event.makerspace, "events"):
            _schedule_checkout(payment)
    except Exception:
        logger.error("Event checkout scheduling failed", extra={"payment_id": payment.pk})
    return payment


def _get_or_create(registration, created_by):
    event = registration.event
    lookup = {
        "makerspace": event.makerspace,
        "subject_type": Payment.SubjectType.EVENT_REGISTRATION,
        "subject_id": registration.pk,
    }
    existing = Payment.objects.filter(**lookup).first()
    if existing is not None:
        return existing
    currency = MakerspacePaymentSettings.for_makerspace(
        event.makerspace
    ).default_currency
    try:
        with transaction.atomic():
            # Routing is stamped now because a purge may later clear the registration's
            # provenance. `payment_via_makerspace` is read FIRST and is the whole point of
            # that column: a waitlisted registration reaches this line only at promotion,
            # potentially after the collaborator purged `events` and nulled the provenance,
            # and falling back to the host would route the charge to a space the visiting
            # member cannot reach.
            return create_payment(
                **lookup,
                member=registration.member,
                via_makerspace=(
                    registration.payment_via_makerspace
                    or registration.registered_via_makerspace
                    or event.makerspace
                ),
                amount=registration_amount(registration),
                currency=currency,
                pricing_snapshot=registration_snapshot(registration),
                created_by=created_by,
                subject_label=event.title,
                due_at=event.starts_at,
            )
    except IntegrityError:
        return Payment.objects.get(**lookup)


def _schedule_checkout(payment):
    def create_safely():
        try:
            create_checkout(payment)
        except Exception:
            logger.error("Event checkout failed", extra={"payment_id": payment.pk})

    transaction.on_commit(create_safely)


def cancel_for_registration(registration, actor, reason_code="registration_cancelled"):
    """Void a pending charge, or open a refund case for a paid one (R6).

    `cancel_or_hold` is its own atomic block, so a failure rolls back only that savepoint
    and the registration change survives; the refund sweep rebuilds a missed case.
    """
    try:
        return cancel_or_hold(
            makerspace=registration.event.makerspace,
            subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id=registration.pk,
            actor=actor,
            reason_code=reason_code,
            cancelled_at=registration.cancelled_at,
        )
    except Exception:
        logger.error("Event charge operation failed", extra={"registration_id": registration.pk})
        return None
