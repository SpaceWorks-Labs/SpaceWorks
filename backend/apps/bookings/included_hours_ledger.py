"""The included-hours ledger of a membership term (decision 221(d)): reads and writes.

Structure (auto decision): TWO pools per plan, `included_booking_hours` for room bookings
and `included_machine_hours` for machine-time bookings, each per membership TERM. A
booking draws from the pool of its resource kind and only from the term that covers its
start, so the term dates are the boundary (a new term is a fresh allowance; unused hours
never roll over). A lifetime term never ends, so it carries no per-term allowance.

Concurrency: every writer first locks the term row (`lock_term`, `FOR UPDATE OF` the term
only) AFTER the room and the member, so two bookings of one member serialise on the term
and the balance each reads is the balance it consumes from. Rows are append-only
(`IncludedHoursUsage`): a booking holds at most one live `consume` row, and a `reverse`
row gives the same minutes back exactly once, so remaining never exceeds the allowance
and never goes below zero.
"""

from django.db.models import Sum
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.models import MembershipTerm
from apps.makerspaces.platform import module_enabled

from .models_included_hours import IncludedHoursUsage

CONSUME, REVERSE = IncludedHoursUsage.Entry.CONSUME, IncludedHoursUsage.Entry.REVERSE


def applies(makerspace):
    """Inert unless the space runs both modules (decision 218: off removes it everywhere)."""
    return module_enabled(makerspace, "membership") and module_enabled(makerspace, "bookings")


def kind_of(space):
    return IncludedHoursUsage.Kind.MACHINE if space.kind == "machine" else IncludedHoursUsage.Kind.BOOKING


def allowance_minutes(term, kind):
    if kind == IncludedHoursUsage.Kind.MACHINE:
        # m7 / decision 218: the machine-hours pool is inert while the machines module is off.
        if not module_enabled(term.plan.makerspace, "machines"):
            return 0
        hours = term.plan.included_machine_hours
    else:
        hours = term.plan.included_booking_hours
    return int(hours or 0) * 60


def terms_for(makerspace, member, at, *, lock=False):
    """The member's active, non-lifetime terms covering `at` (newest first)."""
    rows = MembershipTerm.objects.filter(
        membership__makerspace=makerspace, membership__user=member, membership__status="active",
        status=MembershipTerm.Status.ACTIVE, starts_at__lte=at, ends_at__gt=at,
    ).exclude(plan_type="lifetime").select_related("plan").order_by("-starts_at", "-pk")
    if lock:
        rows = rows.select_for_update(of=("self",))
    return [term for term in rows if not term.is_lifetime]


def lock_term(makerspace, member, space, at):
    """The term a booking at `at` draws from, locked; None when there is nothing to draw."""
    if member is None or not applies(makerspace):
        return None
    kind = kind_of(space)
    for term in terms_for(makerspace, member, at, lock=True):
        if allowance_minutes(term, kind):
            return term
    return None


def used_minutes(term, kind):
    totals = dict(IncludedHoursUsage.objects.filter(term=term, kind=kind).order_by().values_list("entry")
                  .annotate(total=Sum("minutes")))
    return max(0, int(totals.get(CONSUME, 0)) - int(totals.get(REVERSE, 0)))


def live_consumption(booking):
    """The booking's un-reversed consume row, if any (at most one by constraint)."""
    reversed_ids = IncludedHoursUsage.objects.filter(booking=booking, entry=REVERSE).values("reverses_id")
    return IncludedHoursUsage.objects.filter(booking=booking, entry=CONSUME).exclude(
        pk__in=reversed_ids).select_related("term__plan").order_by("-generation").first()


def last_released(booking):
    return IncludedHoursUsage.objects.filter(booking=booking, entry=CONSUME).select_related(
        "term__plan").order_by("-generation").first()


def balance_row(term, kind, *, used=None):
    allowance = allowance_minutes(term, kind)
    used = used_minutes(term, kind) if used is None else used
    return {"kind": kind, "term_id": term.pk, "plan_name": term.plan.name,
            "term_starts_at": term.starts_at.isoformat(), "term_ends_at": term.ends_at.isoformat(),
            "allowance_minutes": allowance, "used_minutes": used,
            "remaining_minutes": max(0, allowance - used)}


def member_balances(makerspace, member, at=None):
    """Every pool of the member's current term(s) that includes hours; [] when inert."""
    if member is None or not applies(makerspace):
        return []
    at = at or timezone.now()
    rows = []
    for term in terms_for(makerspace, member, at):
        for kind in IncludedHoursUsage.Kind.values:
            if allowance_minutes(term, kind):
                rows.append(balance_row(term, kind))
    return rows


def consume(booking, *, actor=None, exempt=False):
    """Take the hours this booking's priced quote used from its term; idempotent per booking.

    Runs inside the creating transaction under `lock_term`, with the booking saved. The
    amount is whatever the quote applied, so the ledger can never disagree with the price.
    """
    from apps.payments.availability import charge_tracking_enabled

    from . import organization_hours
    if organization_hours.organization_of(booking) is not None:
        return organization_hours.consume(booking, actor=actor)  # B13: an organization draws from its own pool
    makerspace = booking.space.makerspace
    if exempt or booking.member_id is None or not applies(makerspace) \
            or not charge_tracking_enabled(makerspace, "bookings"):
        return None
    if live_consumption(booking) is not None:
        return None
    from .service_payments import booking_quote

    info = booking_quote(booking, fresh=True).included_hours
    minutes = int((info or {}).get("applied_minutes") or 0)
    if minutes <= 0:
        return None
    term = MembershipTerm.objects.select_for_update(of=("self",)).get(pk=info["term_id"])
    previous = last_released(booking)
    row = IncludedHoursUsage.objects.create(
        makerspace=makerspace, term=term, booking=booking, kind=info["kind"], entry=CONSUME,
        minutes=minutes, generation=(previous.generation + 1) if previous else 1)
    audit.record(actor or booking.member, "booking.included_hours_consumed", makerspace=makerspace, target=booking,
                 meta={"booking_id": booking.pk, "kind": row.kind, "minutes": minutes})
    return row


def release(booking, actor):
    """Give a rejected/cancelled booking's hours back, exactly once; no-op when none held."""
    from . import organization_hours
    organization_row = organization_hours.release(booking, actor)
    if organization_row is not None:
        return organization_row
    live = live_consumption(booking)
    if live is None:
        return None
    MembershipTerm.objects.select_for_update(of=("self",)).get(pk=live.term_id)
    row = IncludedHoursUsage.objects.create(
        makerspace_id=live.makerspace_id, term_id=live.term_id, booking=booking, kind=live.kind,
        entry=REVERSE, minutes=live.minutes, generation=live.generation, reverses=live)
    audit.record(actor, "booking.included_hours_restored", makerspace=booking.space.makerspace, target=booking,
                 meta={"booking_id": booking.pk, "kind": live.kind, "minutes": live.minutes})
    return row
