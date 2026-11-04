"""Claim policies for release 2 L22's shop routes.

A claim session never buys, cancels or reads a person's shop orders: money and pickup need
the person's own full sign-in. The public catalogue, quote and a guest's status link are
anonymous and ignore a presented claim token.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REASON = "claim sessions cannot buy or manage shop orders"
_ROUTES = (
    ("member-shop-orders", ("GET", "HEAD")),
    ("member-shop-order", ("GET", "HEAD")),
    ("member-shop-order-cancel", ("POST",)),
    ("public-shop-orders", ("POST",)),
)
_ANONYMOUS = ("public-shop", "public-shop-products", "public-shop-product", "public-shop-quote",
              "public-shop-email-code", "public-shop-order-status")

L22_CLAIM_ROUTES = {
    **{(name, method): Refused(_REASON) for name, methods in _ROUTES for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name, _methods in _ROUTES},
    **{(name, method): AnonymousRead() for name in _ANONYMOUS for method in ("GET", "HEAD", "POST", "OPTIONS")},
}
