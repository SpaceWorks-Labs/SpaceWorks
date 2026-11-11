"""Claim policies for the decision-223 (k) member routes: sessions that only prove one claim cannot use them."""

from django.utils.translation import gettext_noop
from apps.accounts.claim_route_types import AnonymousRead, Refused

_MEMBER = (
    ("member-guardian-consents", ("GET", "HEAD")),
    ("member-guardian-consent-sign", ("POST",)),
    ("member-guardian-consent-revoke", ("POST",)),
    ("member-volunteer-hours", ("GET", "HEAD", "POST")),
    ("member-volunteer-credits", ("GET", "HEAD")),
    ("member-join-prefill", ("GET", "HEAD")),
    # Open item A27: a minor reads their own guardian-consent standing.
    ("member-own-guardian-consent", ("GET", "HEAD")),
)

L3B_CLAIM_ROUTES = {
    **{(name, method): Refused(gettext_noop("claim sessions cannot sign guardian consent, log volunteer hours or join"))
       for name, methods in _MEMBER for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _MEMBER},
}
