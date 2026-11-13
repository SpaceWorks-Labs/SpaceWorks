"""Claim policies for release 2 L3's holder card routes and the public card check.

A claim session never reads or acts on a person's cards (no downloads, email, photo,
wallet pass or check-link changes). The public card check ignores a presented claim
token: it is an anonymous read.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REASON = "claim sessions cannot read or act on a person's cards"
_ROUTES = (
    ("member-cards", ("GET", "HEAD")),
    ("member-card-download", ("GET", "HEAD")),
    ("member-card-face", ("GET", "HEAD")),
    ("member-card-font", ("GET", "HEAD")),
    ("member-card-email", ("POST",)),
    ("member-card-settings", ("GET", "HEAD", "PATCH")),
    ("member-card-rotate-link", ("POST",)),
    ("member-card-holder-photo", ("POST", "PUT", "DELETE")),
    ("member-card-photo-cleanup", ("POST",)),
    ("member-card-photo-accept", ("POST",)),
    ("member-card-photo-discard", ("POST",)),
    ("member-card-wallet", ("POST",)),
    ("member-guest-pass-wallet", ("POST",)),
    ("member-card-job", ("GET", "HEAD")),
    ("member-card-job-result", ("GET", "HEAD")),
    ("member-id-programme-invite-accept", ("POST",)),
    ("member-event-registration-ticket", ("GET", "HEAD")),
    ("public-id-programme", ("GET", "HEAD")),
    ("public-id-programme-join", ("POST",)),
    ("public-id-programme-join-photo", ("POST",)),
    ("public-id-programme-prefill", ("GET", "HEAD")),
)

L3_CLAIM_ROUTES = {
    **{(name, method): Refused(_REASON) for name, methods in _ROUTES for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _ROUTES},
    **{(name, method): AnonymousRead() for name in ("public-card-verification", "public-organization-id-programmes")
       for method in ("GET", "HEAD", "OPTIONS")},
}
