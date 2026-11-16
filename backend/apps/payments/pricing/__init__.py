"""The pricing kernel (lane L15, decisions #84/#85). The contract other lanes call:

* `quote(makerspace, domain, target=None, member=None, params=None) -> Quote` -- the one
  resolver (see `resolver.py` for the targets and params per domain).
* `verify_digest(quote, digest)` -- raises 409 `price_changed` (with the new quote) when
  a submit carries a digest the current price no longer matches (A8).
* `best_discount(makerspace, domain, member, quote)` -- the member's one best automatic
  discount, for a lane that builds its own lines (L6 ticket orders, L22 shop) before any
  promo code is applied on top (A3).
* `Quote.to_snapshot()` -> what `create_payment(..., pricing_snapshot=...)` freezes.

Imports are lazy so `apps.payments.models` never imports the kernel at load time.
"""


def quote(*args, **kwargs):
    from apps.payments.pricing.resolver import quote as resolve
    return resolve(*args, **kwargs)


def best_discount(*args, **kwargs):
    from apps.payments.pricing.discounts import best_discount as apply_best
    return apply_best(*args, **kwargs)


def verify_digest(current, digest):
    """A8: a submit that carries the digest it was shown is refused when the price moved."""
    from apps.payments.pricing.errors import PriceChanged
    if digest and digest != current.digest:
        from apps.payments.pricing.serializers import quote_payload
        raise PriceChanged(quote=quote_payload(current))
    return current


__all__ = ["best_discount", "quote", "verify_digest"]
