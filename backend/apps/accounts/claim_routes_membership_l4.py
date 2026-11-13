"""Claim policies for the release-2 L4 membership lifecycle routes."""

from django.utils.translation import gettext_noop
from apps.accounts.claim_route_types import AnonymousRead, Refused

_MEMBER = (
    ("member-membership-consents", ("GET", "HEAD", "POST", "DELETE")),
    ("member-membership-history", ("GET", "HEAD")),
    ("member-erasure-requests", ("GET", "HEAD", "POST")),
    ("member-erasure-request-withdraw", ("POST",)),
    ("member-refund-suggestion", ("GET", "HEAD")),
)
_PUBLIC = ("public-membership-plans", "public-membership-plan-detail", "public-membership-invite")

L4_CLAIM_ROUTES = {
    **{(name, method): Refused(gettext_noop("claim sessions cannot manage consent, erasure, history or refunds"))
       for name, methods in _MEMBER for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _MEMBER},
    **{(name, method): AnonymousRead() for name in _PUBLIC for method in ("GET", "HEAD", "OPTIONS")},
}
