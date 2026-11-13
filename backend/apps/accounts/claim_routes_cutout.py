"""Claim policy for decision 314(c)'s holder cut-out route: a claim session never acts on a person's card photo."""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REASON = "claim sessions cannot read or act on a person's cards"
_METHODS = ("GET", "HEAD", "POST", "PATCH", "PUT", "DELETE")

CUTOUT_CLAIM_ROUTES = {
    **{("member-card-photo-cutout", method): Refused(_REASON) for method in _METHODS},
    ("member-card-photo-cutout", "OPTIONS"): AnonymousRead(),
}
