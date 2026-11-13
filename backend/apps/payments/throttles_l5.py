"""Rate limits for the payer-facing L5 endpoints (claims and public pay links)."""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class PaymentClaimThrottle(UserRateThrottle):
    scope = "payment_claims"


class PayLinkThrottle(AnonRateThrottle):
    scope = "pay_links"
