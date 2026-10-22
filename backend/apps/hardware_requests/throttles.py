"""Abuse budgets for account-less borrow requests (owner decision #80).

Only a space without member accounts takes these paths. Both IP budgets self-select by
auth state so they can sit beside the member principal throttle without rate-limiting a
makerspace's signed-in staff by their shared egress IP.
"""

from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.audit_events import fingerprint


class _AnonymousIpThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            return None
        ident = self.get_ident(request)
        return None if not ident else self.cache_format % {"scope": self.scope, "ident": ident}


class AnonymousRequestIpBurstThrottle(_AnonymousIpThrottle):
    scope = "anonymous_request_ip_burst"


class AnonymousRequestIpHourThrottle(_AnonymousIpThrottle):
    scope = "anonymous_request_ip_hour"


class AnonymousRequestEmailThrottle(SimpleRateThrottle):
    """Per-address budget for email-code sends, keyed on a fingerprint, never the address."""

    scope = "anonymous_request_email"

    def get_cache_key(self, request, view):
        email = str(getattr(request, "anonymous_contact_email", "") or "").strip().lower()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": fingerprint(email)}
