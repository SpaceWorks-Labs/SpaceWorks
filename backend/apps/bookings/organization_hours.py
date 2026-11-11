"""Open item B13: the organization hours bank, as the booking price path sees it.

An organization booking (decision 223 (k)) draws its included hours from the ORGANIZATION's pool at the space,
never from the contact member's plan, and only the remainder is charged. This module mirrors
`included_hours` / `included_hours_ledger` (the member term ledger) for that pool:

* `quote_allowance` is called by `included_hours.quote_allowance` BEFORE the price is built, so the quote, the
  staff preview and the charge all show the same applied and remaining hours.
* `consume` / `release` / `retake_for_move` are called from the same seams as the member ledger (create,
  reject/cancel, restore, time edit). Rows are append-only (`OrganizationHoursLedger`).
* The balance is derived: allowance + grants and adjustments - net consumption, for ONE period (`period_key`).
  A booking always draws from the period its start falls in; unused hours never roll over.

Concurrency: every writer locks the allowance row first (`lock_bank`), after the room, so two bookings of one
organization serialise and the balance each reads is the balance it consumes from. Money is never computed here.
"""
from datetime import datetime, timezone as dt_timezone

from django.db.models import Sum

from apps.audit import services as audit
from apps.makerspaces.platform import module_enabled

from .included_hours_ledger import kind_of
from .models_organization_hours import OrganizationHoursAllowance, OrganizationHoursLedger

CONSUME, RELEASE = OrganizationHoursLedger.Entry.CONSUME, OrganizationHoursLedger.Entry.RELEASE
SOURCE = "organization"


def applies(makerspace):
    """Inert unless bookings and the organization-bookings switch are both on (decision 218)."""
    from .organization_booking import organization_bookings_on
    return module_enabled(makerspace, "bookings") and organization_bookings_on(makerspace)


def organization_of(booking):
    """The organization a saved booking was made for, or None (also None once the organization is gone)."""
    if booking is None or booking.pk is None:
        return None
    from .models_organization import BookingOrganizationLink
    link = BookingOrganizationLink.objects.filter(booking_id=booking.pk).select_related("organization").first()
    return link.organization if link is not None else None


def period_key(period, at):
    at = at.astimezone(dt_timezone.utc)
    if period == OrganizationHoursAllowance.Period.MONTHLY:
        return f"{at:%Y-%m}"
    if period == OrganizationHoursAllowance.Period.YEARLY:
        return f"{at:%Y}"
    return "all"


def period_ends_at(period, at):
    """ISO end of the period containing `at` (UTC), or '' for a pool that never resets."""
    at = at.astimezone(dt_timezone.utc)
    if period == OrganizationHoursAllowance.Period.MONTHLY:
        year, month = (at.year + 1, 1) if at.month == 12 else (at.year, at.month + 1)
        return datetime(year, month, 1, tzinfo=dt_timezone.utc).isoformat()
    if period == OrganizationHoursAllowance.Period.YEARLY:
        return datetime(at.year + 1, 1, 1, tzinfo=dt_timezone.utc).isoformat()
    return ""


def bank(makerspace, organization, *, lock=False):
    rows = OrganizationHoursAllowance.objects.filter(makerspace=makerspace, organization=organization)
    return (rows.select_for_update() if lock else rows).first()


def lock_bank(makerspace, organization):
    """Serialise writers of one organization's pool; None when no allowance exists."""
    if organization is None or not applies(makerspace):
        return None
    return bank(makerspace, organization, lock=True)


def totals(makerspace, organization, key):
    """`(pool_minutes, used_minutes)` of one period: pool = allowance + grants + adjustments."""
    allowance = bank(makerspace, organization)
    sums = dict(OrganizationHoursLedger.objects.filter(
        makerspace=makerspace, organization=organization, period_key=key).order_by().values_list("entry")
        .annotate(total=Sum("minutes")))
    extra = int(sums.get("grant", 0)) + int(sums.get("adjust", 0))
    used = max(0, -(int(sums.get(CONSUME, 0)) + int(sums.get(RELEASE, 0))))
    return (allowance.allowance_minutes if allowance else 0) + extra, used


def live_consumption(booking):
    released = OrganizationHoursLedger.objects.filter(booking=booking, entry=RELEASE).values("reverses_id")
    return OrganizationHoursLedger.objects.filter(booking=booking, entry=CONSUME).exclude(
        pk__in=released).order_by("-generation").first()


def last_consumed(booking):
    return OrganizationHoursLedger.objects.filter(booking=booking, entry=CONSUME).order_by("-generation").first()


def _row(allowance, organization, key, kind, at, *, held=0, cap=None):
    pool, used = totals(allowance.makerspace_id, organization, key)
    if pool <= 0 and not held:
        return None
    other = used - held
    available = max(0, pool - other)
    if cap is not None:
        available = min(available, cap)
    return {"kind": kind, "term_id": None, "plan_name": organization.name, "source": SOURCE,
            "organization_id": organization.pk, "period_key": key,
            "term_ends_at": period_ends_at(allowance.period, at), "allowance_minutes": pool,
            "used_minutes": other, "available_minutes": available}


def quote_allowance(makerspace, space, organization, params):
    """The per-quote allowance dict the price builder consumes, or None (nothing included)."""
    starts_at = params.get("starts_at")
    if starts_at is None or not applies(makerspace):
        return None
    allowance = bank(makerspace, organization)
    if allowance is None:
        return None
    kind = kind_of(space)
    booking = params.get("booking")
    if booking is not None and booking.pk is not None:
        live = live_consumption(booking)
        if live is not None:  # a saved booking is priced from its OWN live row, so re-quotes are stable
            return _row(allowance, organization, live.period_key, kind, starts_at, held=-live.minutes)
        previous = last_consumed(booking) if booking.status == "cancelled" else None
        if previous is None:
            return None
        return _row(allowance, organization, previous.period_key, kind, starts_at, cap=-previous.minutes)
    return _row(allowance, organization, period_key(allowance.period, starts_at), kind, starts_at)


def consume(booking, *, actor=None):
    """Take the hours this booking's priced quote used from the pool; idempotent per booking."""
    from apps.payments.availability import charge_tracking_enabled

    makerspace = booking.space.makerspace
    organization = organization_of(booking)
    if organization is None or booking.member_id is None or not applies(makerspace) \
            or not charge_tracking_enabled(makerspace, "bookings"):
        return None
    if lock_bank(makerspace, organization) is None or live_consumption(booking) is not None:
        return None
    from .service_payments import booking_quote

    info = booking_quote(booking, fresh=True, organization=organization).included_hours or {}
    minutes = int(info.get("applied_minutes") or 0) if info.get("source") == SOURCE else 0
    if minutes <= 0:
        return None
    previous = last_consumed(booking)
    row = OrganizationHoursLedger.objects.create(
        makerspace=makerspace, organization=organization, booking=booking, entry=CONSUME, minutes=-minutes,
        period_key=info["period_key"], generation=(previous.generation + 1) if previous else 1, actor=actor)
    audit.record(actor or booking.member, "booking.org_hours_consumed", makerspace=makerspace, target=booking,
                 meta={"booking_id": booking.pk, "organization_id": organization.pk, "minutes": minutes})
    from .organization_hours_notice import alert_if_needed
    alert_if_needed(makerspace, organization, info["period_key"], *totals(makerspace, organization, info["period_key"]))
    return row


def release(booking, actor):
    """Give a rejected/cancelled/moved booking's hours back, exactly once; None when none are held."""
    live = live_consumption(booking)
    if live is None:
        return None
    OrganizationHoursAllowance.objects.select_for_update().filter(
        makerspace_id=live.makerspace_id, organization_id=live.organization_id).first()
    row = OrganizationHoursLedger.objects.create(
        makerspace_id=live.makerspace_id, organization_id=live.organization_id, booking=booking, entry=RELEASE,
        minutes=-live.minutes, period_key=live.period_key, generation=live.generation, reverses=live, actor=actor)
    audit.record(actor, "booking.org_hours_released", makerspace=booking.space.makerspace, target=booking,
                 meta={"booking_id": booking.pk, "organization_id": live.organization_id, "minutes": -live.minutes})
    return row


def retake_for_move(space, locked, *, actor, price_confirmation=None):
    """A moved/edited booking releases its hours and takes what the NEW time needs from the pool.

    The same guard as the member move (decision 226(d)): a different period, or more hours than the booking
    held, needs a matching staff price confirmation or the whole transaction answers 409 `price_changed`."""
    from apps.payments.availability import charge_tracking_enabled

    makerspace, organization = space.makerspace, organization_of(locked)
    if organization is None or locked.member_id is None or not applies(makerspace) \
            or not charge_tracking_enabled(makerspace, "bookings"):
        return None
    live = live_consumption(locked)
    if lock_bank(makerspace, organization) is None or live is None:
        return None
    held, key = -live.minutes, live.period_key
    release(locked, actor)
    from .service_payments import booking_quote

    info = booking_quote(locked, fresh=True, organization=organization).included_hours or {}
    if info.get("period_key") != key or int(info.get("applied_minutes") or 0) > held:
        from .staff_price_confirmation import verify
        verify(space, locked.member, locked.starts_at, locked.ends_at, price_confirmation or "",
               organization=organization)
    return consume(locked, actor=actor)

