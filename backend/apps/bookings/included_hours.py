"""Included plan hours as the pricing kernel and the booking services see them (decision 221(d)).

`payments.pricing.resolver.quote` calls `quote_allowance` BEFORE building a booking's price
and `summarize` after, so the quote, the staff price preview, the public/member quote and
the charge all show the same applied and remaining hours. The ledger itself lives in
`included_hours_ledger`; this module never writes money.

A saved booking is priced from its OWN live consume row only (never a fresh allowance), so
re-quotes (approval, price-drop scan) are stable; an unsaved booking (preview, creation)
reads the member's remaining balance. A booking whose room has no hourly rate uses nothing.

Event-venue bookings (auto decision): a replacement of an event-linked reservation made BY
STAFF for a member draws nothing from that member's hours; the member booking for
themselves does. A booking linked to an event after it was created keeps what it used.
"""

from decimal import Decimal

from apps.makerspaces.platform import module_enabled

from .included_hours_ledger import (
    allowance_minutes, applies, balance_row, kind_of, last_released, live_consumption, lock_term,
    member_balances, terms_for, used_minutes,
)
from .models import Booking
from .models_included_hours import IncludedHoursUsage

__all__ = ["event_venue_exempt", "lock_term", "member_balances", "preview_summary", "quote_allowance",
           "summarize"]


def event_venue_exempt(space, member, actor, replaces):
    """True when a replacement of an event-linked booking is staff-made for another member."""
    if replaces is None or member is None or actor is None or getattr(actor, "pk", None) == member.pk:
        return False
    if not module_enabled(space.makerspace, "events"):
        return False
    from apps.events.models import EventBookingDecision, EventMachineBookingLink

    return (EventBookingDecision.objects.filter(booking_id=replaces.pk).exists()
            or EventMachineBookingLink.objects.filter(booking_id=replaces.pk, unlinked_at__isnull=True).exists())


def _row(term, kind, other_used, available):
    base = balance_row(term, kind, used=other_used)
    return {"kind": kind, "term_id": term.pk, "plan_name": base["plan_name"],
            "term_ends_at": base["term_ends_at"], "allowance_minutes": base["allowance_minutes"],
            "used_minutes": other_used, "available_minutes": max(0, available)}


def quote_allowance(makerspace, space, member, params):
    """The per-quote allowance dict the price builder consumes, or None (nothing included)."""
    organization = params.get("organization")
    if organization is not None:  # B13: an organization booking draws from the organization's pool only
        from .organization_hours import quote_allowance as organization_allowance
        return organization_allowance(makerspace, space, organization, params)
    if member is None or params.get("included_exempt") or not applies(makerspace) \
            or params.get("starts_at") is None:
        return None
    kind = kind_of(space)
    booking = params.get("booking")
    if booking is not None and booking.pk is not None:
        live = live_consumption(booking)
        if live is not None:
            held = used_minutes(live.term, kind) - live.minutes
            return _row(live.term, kind, held, live.minutes) if live.kind == kind else None
        released = last_released(booking) if booking.status == Booking.Status.CANCELLED else None
        if released is None or released.kind != kind:
            return None
        # A cancellation being undone: the same hours back, if they are still free.
        used = used_minutes(released.term, kind)
        return _row(released.term, kind, used,
                    min(released.minutes, allowance_minutes(released.term, kind) - used))
    for term in terms_for(makerspace, member, params["starts_at"]):
        total = allowance_minutes(term, kind)
        if total:
            used = used_minutes(term, kind)
            return _row(term, kind, used, total - used)
    return None


def summarize(allowance, lines):
    """What the quote shows: hours applied now and the balance left after this booking."""
    applied = int(allowance.get("applied_minutes", 0))
    left = max(0, allowance["allowance_minutes"] - allowance["used_minutes"] - applied)
    extra = {k: allowance[k] for k in ("source", "organization_id", "period_key") if k in allowance}
    return {**{k: allowance[k] for k in ("kind", "term_id", "plan_name", "term_ends_at", "allowance_minutes")},
            **extra,
            "applied_minutes": applied, "applied_hours": str((Decimal(applied) / 60).quantize(Decimal("0.01"))),
            "remaining_minutes": left, "remaining_hours": str((Decimal(left) / 60).quantize(Decimal("0.01")))}


def preview_summary(space, member, starts_at, *, priced=None):
    """Staff preview block: the quote's own summary, else the member's balance (charges off)."""
    if priced is not None and priced.included_hours:
        return priced.included_hours
    allowance = quote_allowance(space.makerspace, space, member, {"starts_at": starts_at})
    if allowance is None:
        return None
    allowance["applied_minutes"] = 0
    return summarize(allowance, ())
