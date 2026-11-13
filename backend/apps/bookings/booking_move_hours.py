"""Decision 226(d): moving a booking releases and re-takes its included plan hours for the NEW time.

Runs inside the move's locked transaction, after the new window passed admission. The old
consume row is reversed (append-only ledger), the new time is priced from the member's balance
as if the booking did not exist yet, and a fresh consume row is written, so minute rounding and
the per-day cap are exactly the pricing kernel's, applied at the new time.

A move that changes the TERM the hours come from (or that needs more included hours than the
booking held) is not applied silently: it needs a staff price confirmation digest, the same one
`staff_price_confirmation` issues. Without a matching digest the move answers 409 `price_changed`
with the fresh preview and the whole transaction (reversal included) rolls back. A booking
that holds no included hours is untouched.
"""
from apps.payments.availability import charge_tracking_enabled

from . import included_hours
from .included_hours_ledger import applies, consume, live_consumption, release
from .service_payments import booking_quote


def retake_hours_for_move(space, locked, *, actor, price_confirmation=None):
    from . import organization_hours
    if organization_hours.organization_of(locked) is not None:  # B13: the organization's pool, not the member's plan
        return organization_hours.retake_for_move(space, locked, actor=actor, price_confirmation=price_confirmation)
    makerspace = space.makerspace
    if locked.member_id is None or not applies(makerspace) or not charge_tracking_enabled(makerspace, "bookings"):
        return None
    live = live_consumption(locked)
    if live is None:
        return None
    included_hours.lock_term(makerspace, locked.member, space, locked.starts_at)
    held_minutes, held_term = live.minutes, live.term_id
    release(locked, actor)
    info = booking_quote(locked, fresh=True).included_hours or {}
    applied = int(info.get("applied_minutes") or 0)
    if info.get("term_id") != held_term or applied > held_minutes:
        from .staff_price_confirmation import verify
        verify(space, locked.member, locked.starts_at, locked.ends_at, price_confirmation or "")
    return consume(locked, actor=actor)
