from collections.abc import Mapping

from rest_framework.throttling import SimpleRateThrottle


class HostingRequestEmailThrottle(SimpleRateThrottle):
    """Per-address submission budget, checked manually AFTER validation.

    Never listed in ``throttle_classes``: an overflow must look exactly like success
    (same 202, nothing stored, no mail), so the view calls ``allow_request`` itself.
    The cache key is a keyed fingerprint, never the address.
    """

    scope = "hosting_request_email"

    def get_cache_key(self, request, view):
        from apps.accounts.audit_events import fingerprint

        data = request.data if isinstance(request.data, Mapping) else {}
        email = str(data.get("applicant_email") or "").strip().lower()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": fingerprint(email)}
