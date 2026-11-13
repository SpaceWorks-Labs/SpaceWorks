"""The two deployment switches of the managed-hosting limiter (#187A), both off by default.

* The hosting switch (superadmin console; ``MANAGED_PLANS_ENABLED`` is its optional legacy
  override): plans, trials, recorded hosting billing and fair-use limits, on any install.
* ``MANAGED_BILLING_ONLINE_ENABLED``: online checkout of hosting invoices through the
  platform's own Stripe/Razorpay account. Meaningless unless plans are on.
"""

from django.conf import settings
from django.http import Http404


def hosting_switch_forced() -> bool:
    """True when the operator set ``MANAGED_PLANS_ENABLED`` (legacy preset): it overrides the console switch."""
    return getattr(settings, "MANAGED_PLANS_ENABLED", None) is not None


def hosting_enabled() -> bool:
    """One switch for plans, fair-use limits, hosting requests and the platform fallbacks (#234).

    The env value, when set, forces the answer; otherwise the superadmin's console switch
    (``PlatformHostingBillingSettings.hosting_enabled``, default off) decides. Never raises:
    an unreachable table or a DB-less caller means "off".
    """
    forced = getattr(settings, "MANAGED_PLANS_ENABLED", None)
    if forced is not None:
        return bool(forced)
    try:
        from .models import PlatformHostingBillingSettings

        return bool(PlatformHostingBillingSettings.objects.filter(pk=1)
                    .values_list("hosting_enabled", flat=True).first())
    except Exception:  # noqa: BLE001 - off is the safe answer
        return False


def plans_enabled() -> bool:
    return hosting_enabled()


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
