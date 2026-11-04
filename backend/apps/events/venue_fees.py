"""Venue fees for hosting (release 2 L6, #128 C-20, Q-V1 (a)): configure, preview, charge.

Staff with event management set who pays (a person's account -- a member running their
own event, or a co-hosting organisation's contact), an optional room and Free / Custom /
Inherit. The amount always comes from `pricing.quote("events", event, params=
{"venue_fee": row})`, never computed here. The fee is charged ONCE: when the event is
published (confirmed), or earlier by an explicit staff "Charge now". It is one `Payment`
(subject `event_venue_fee`, events income) through the record-first ledger seam; a quote
of 0 raises nothing and is audited. After charging the row is frozen: staff waive or
refund it only through the existing payment decisions (#59).
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record

from .feature_gates import require_feature
from .models import EventVenueFee
from .orders_errors import OrderRefused

logger = logging.getLogger(__name__)
FIELDS = ("payer", "organization", "room", "mode", "basis", "amount")


def venue_quote(event, fee):
    from apps.payments.pricing import quote
    return quote(event.makerspace, "events", event, params={"venue_fee": fee}, discounts=False)


@transaction.atomic
def configure(event, *, actor, **values):
    from apps.accounts.account_kind_guards import require_member_account
    from .services import _locked_event
    event = _locked_event(event.pk)
    require_feature(event, "events.venue_fees")
    fee = EventVenueFee.objects.select_for_update().filter(event=event).first()
    if fee is not None and fee.status == EventVenueFee.Status.CHARGED:
        raise OrderRefused("venue_fee_charged", "The venue fee was already charged; settle or waive that charge.")
    require_member_account(values["payer"])
    room = values.get("room")
    if room is not None and room.makerspace_id != event.makerspace_id:
        raise OrderRefused("venue_fee_charged", "Choose a room of this space.")
    fee = fee or EventVenueFee(makerspace=event.makerspace, event=event)
    for key in FIELDS:
        if key in values:
            setattr(fee, key, values[key])
    if fee.mode != EventVenueFee.Mode.CUSTOM:
        fee.amount = None
    fee.status, fee.updated_by = EventVenueFee.Status.CONFIGURED, actor
    fee.full_clean(exclude=("makerspace", "event"))
    fee.save()
    record(actor, "event.venue_fee_configured", makerspace=event.makerspace, target=fee,
           meta={"event_id": event.pk, "mode": fee.mode, "basis": fee.basis, "room_id": fee.room_id,
                 "payer_id": fee.payer_id, "organization_id": fee.organization_id})
    return fee


@transaction.atomic
def charge(event, *, actor):
    """Raise the venue-fee charge now. Returns `(fee, payment_or_None)`."""
    from apps.payments.availability import charge_tracking_enabled
    from apps.payments.models import Payment
    from apps.payments.pricing.charging import raise_priced
    from .services import _locked_event
    event = _locked_event(event.pk)
    require_feature(event, "events.venue_fees")
    fee = EventVenueFee.objects.select_for_update().filter(event=event).first()
    if fee is None or fee.status != EventVenueFee.Status.CONFIGURED:
        raise OrderRefused("venue_fee_charged", "There is no venue fee waiting to be charged.")
    if not charge_tracking_enabled(event.makerspace, "events"):
        raise OrderRefused("order_not_payable", "This space is not taking payments for events.")
    priced = venue_quote(event, fee)
    payment = raise_priced(priced, makerspace=event.makerspace, subject_type=Payment.SubjectType.EVENT_VENUE_FEE,
                           subject_id=fee.pk, member=fee.payer, created_by=actor or fee.payer, target=fee,
                           subject_label=f"Venue fee - {event.title}"[:255], due_at=event.starts_at)
    fee.status = EventVenueFee.Status.CHARGED if payment is not None else EventVenueFee.Status.FREE
    fee.charged_at = timezone.now()
    fee.save(update_fields=["status", "charged_at", "updated_at"])
    record(actor, "event.venue_fee_charged", makerspace=event.makerspace, target=fee,
           meta={"event_id": event.pk, "payment_id": getattr(payment, "pk", None), "total": str(priced.total)})
    return fee, payment


def on_event_published(event, actor):
    """Lane L6 hook from `services_lifecycle.publish`: the event is confirmed, charge its fee."""
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(event.makerspace, "events.venue_fees"):
        return
    if not EventVenueFee.objects.filter(event=event, status=EventVenueFee.Status.CONFIGURED).exists():
        return

    def run():
        try:
            charge(event, actor=actor)
        except Exception:
            logger.error("event_venue_fee_charge_failed", extra={"event_id": event.pk})

    transaction.on_commit(run)
