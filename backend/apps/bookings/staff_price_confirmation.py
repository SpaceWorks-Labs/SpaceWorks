"""Staff price confirmation (decision 216): one preview binds room, member, window and charge mode.

A staff preview authorizes the exact room, member and window before it shows a price,
then returns the quote the locked create will charge plus a confirmation digest over
all of those inputs. The locked create recomputes the confirmation AFTER locked
authorization and admission and refuses a stale digest with 409 `price_changed`
before any booking or debt is written; the verified quote is the one frozen on a
pending booking or charged on an instant one. Charges switched off are part of the
digest, so flipping charge tracking forces a fresh confirmation.

No pricing lives here: the amount always comes from `service_payments.booking_quote`
(-> `payments.pricing.quote()`), exactly as every other booking charge.
"""

import hashlib
import hmac
import json
from datetime import timezone as dt_timezone

from apps.payments.availability import charge_tracking_enabled
from apps.payments.pricing.errors import PriceChanged
from apps.payments.pricing.serializers import quote_payload

from .models import Booking
from .service_payments import booking_quote

TRACKED, CHARGES_OFF = "tracked", "off"


def confirmed_quote(space, member, starts_at, ends_at, exempt=False, organization=None):
    """`(charges, priced)`; `priced` is None when the space tracks no booking charges.

    Plan included hours (decision 221(d)) are applied inside `booking_quote`, so the digest
    below moves when the member's balance does and a stale preview is refused."""
    if not charge_tracking_enabled(space.makerspace, "bookings"):
        return CHARGES_OFF, None
    probe = Booking(space=space, member=member, starts_at=starts_at, ends_at=ends_at)
    return TRACKED, booking_quote(probe, member, exempt=exempt, organization=organization)


def confirmation_digest(space, member, starts_at, ends_at, charges, priced):
    body = {
        "version": 1, "space_id": space.pk, "member_id": getattr(member, "pk", None),
        "starts_at": starts_at.astimezone(dt_timezone.utc).isoformat(),
        "ends_at": ends_at.astimezone(dt_timezone.utc).isoformat(),
        "charges": charges, "quote": priced.digest if priced is not None else None,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _payload(space, member, starts_at, ends_at, charges, priced, exempt=False, organization=None):
    from .included_hours import preview_summary

    # B13: an organization booking shows the organization bank's own applied/remaining hours.
    included = (priced.included_hours if priced is not None else None) if organization is not None else (
        None if exempt else preview_summary(space, member, starts_at, priced=priced))
    return {
        "charges": charges,
        "included_hours": included,
        "quote": quote_payload(priced) if priced is not None else None,
        "price_confirmation": confirmation_digest(space, member, starts_at, ends_at, charges, priced),
    }


def preview(space, member, starts_at, ends_at, exempt=False, organization=None):
    """The staff-visible quote. Callers have already authorized room, member and window."""
    charges, priced = confirmed_quote(space, member, starts_at, ends_at, exempt, organization)
    return _payload(space, member, starts_at, ends_at, charges, priced, exempt, organization)


def verify(space, member, starts_at, ends_at, digest, exempt=False, organization=None):
    """Inside the locked create: the quote to freeze/charge, or 409 with the fresh preview."""
    charges, priced = confirmed_quote(space, member, starts_at, ends_at, exempt, organization)
    expected = confirmation_digest(space, member, starts_at, ends_at, charges, priced)
    if not hmac.compare_digest(str(digest), expected):
        raise PriceChanged(confirmation=_payload(space, member, starts_at, ends_at, charges, priced, exempt, organization))
    return priced
