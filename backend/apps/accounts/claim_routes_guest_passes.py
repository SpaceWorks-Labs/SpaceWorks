"""Claim policies for the decision-223 guest-pass routes: sessions that only prove one claim cannot use them."""

from django.utils.translation import gettext_noop
from apps.accounts.claim_route_types import AnonymousRead, Refused

_MEMBER = (
    ("member-guest-passes", ("GET", "HEAD")),
    ("member-guest-pass-waiver", ("POST",)),
    ("member-sponsored-guests", ("GET", "HEAD", "POST")),
    ("member-sponsored-guest-revoke", ("POST",)),
    ("member-day-passes", ("GET", "HEAD")),
    ("member-day-pass-purchase", ("POST",)),
)

GUEST_PASS_CLAIM_ROUTES = {
    **{(name, method): Refused(gettext_noop("claim sessions cannot hold, sponsor or buy guest passes"))
       for name, methods in _MEMBER for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _MEMBER},
    **{("public-day-passes", method): AnonymousRead() for method in ("GET", "HEAD", "OPTIONS")},
}
