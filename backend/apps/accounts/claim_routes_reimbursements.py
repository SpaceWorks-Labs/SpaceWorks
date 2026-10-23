"""Claim policy for reimbursement, stage-form and payout owner routes.

Every owner command and read needs a full authenticated member session; a claimed or
pre-authentication session is refused. OPTIONS stays an anonymous CORS preflight, as on
every other member route.
"""
from .claim_route_types import AnonymousRead, Refused
from .reimbursement_route_catalog import ROUTES

_REFUSED = Refused("A full authenticated account is required for reimbursement, stage-form and payout work.")

CLAIM_ROUTES = {
    **{(name, method): _REFUSED
       for name, methods, target, surface in ROUTES if surface == "member" for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, methods, target, surface in ROUTES if surface == "member"},
}
