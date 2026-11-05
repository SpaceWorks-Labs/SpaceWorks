"""The two deployment switches of the managed-hosting limiter (#187A), both off by default.

* ``MANAGED_PLANS_ENABLED``: plans, trials and recorded hosting billing. It also needs a
  managed deployment (``PLATFORM_DOMAIN_SUFFIX`` set), like every fair-use limit.
* ``MANAGED_BILLING_ONLINE_ENABLED``: online checkout of hosting invoices through the
  platform's own Stripe/Razorpay account. Meaningless unless plans are on.
"""

from django.conf import settings
from django.http import Http404


def plans_enabled() -> bool:
    if not getattr(settings, "MANAGED_PLANS_ENABLED", False):
        return False
    from apps.makerspaces import domain_verification

    return not domain_verification.is_self_host()


def online_billing_enabled() -> bool:
    return plans_enabled() and bool(getattr(settings, "MANAGED_BILLING_ONLINE_ENABLED", False))


def require_plans_enabled():
    if not plans_enabled():
        raise Http404()


def require_online_billing():
    if not online_billing_enabled():
        raise Http404()


def public_base_url() -> str:
    return str(getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").strip().rstrip("/")
