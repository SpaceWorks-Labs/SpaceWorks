"""Claim policies for release 2 L18's member and public routes (donations, sponsors, calendar links).

A claim session never reads or changes someone's gifts, pledges or calendar links: those are a
person's own money and disclosure capabilities, so they need the person's full sign-in. The
public donation page, giving, the sponsor walls, a guest's signed links and the bearer calendar
feeds are anonymous routes that ignore a presented claim token.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REASON = "claim sessions cannot read or change a person's gifts, pledges or calendar links"
_MEMBER = (
    ("member-donations", ("GET", "HEAD")),
    ("member-donation-tax-receipt", ("GET", "HEAD")),
    ("member-pledges", ("GET", "HEAD")),
    ("member-pledge", ("POST",)),
    ("member-personal-calendar-feed", ("GET", "HEAD", "POST", "DELETE")),
)
_PUBLIC = (
    ("public-donation-page", ("GET", "HEAD")),
    ("public-donations", ("POST",)),
    ("public-donation-email-code", ("POST",)),
    ("public-donation-pledges", ("POST",)),
    ("public-sponsor-wall", ("GET", "HEAD")),
    ("public-event-sponsors", ("GET", "HEAD")),
    ("public-donation-status", ("GET", "HEAD")),
    ("public-donation-checkout", ("POST",)),
    ("public-donation-tax-receipt", ("GET", "HEAD")),
    ("public-pledge-manage", ("GET", "HEAD", "POST")),
    ("public-shift-calendar-feed", ("GET", "HEAD")),
    ("public-combined-calendar-feed", ("GET", "HEAD")),
    ("public-listed-events-calendar", ("GET", "HEAD")),
)

L18_CLAIM_ROUTES = {
    **{(name, method): Refused(_REASON) for name, methods in _MEMBER for method in methods},
    **{(name, method): AnonymousRead() for name, methods in _PUBLIC for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in (*_MEMBER, *_PUBLIC)},
}
