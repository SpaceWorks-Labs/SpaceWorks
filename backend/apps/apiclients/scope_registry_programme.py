"""Closed programme route policy; session-only staff commands grant no API-key authority."""
from apps.accounts.programme_route_catalog import ROUTES
from apps.separability.registry import runtime_active


SESSION_ONLY = frozenset(name for name, methods, target in ROUTES
    if name.startswith(("events-programme-admin-", "events-programme-tenant-admin-", "events-programme-library-"))
    or name in {"events-programme-series-guests", "admin-platform-insights"})


# Only routes behind the HMAC-protected `/api/v1/public/` prefix are API-client
# routes. Member (`/api/v1/member/`) and account vault routes are session-owned:
# registering them would be stale drift under the default prefixes and, on a
# deployment that extends the prefixes, hand tenant API keys owner surfaces.
PROTECTED = "events-programme-public-"


def definitions(read, write, global_target, tenant_target):
    result = []
    for name, methods, target in ROUTES:
        if not name.startswith(PROTECTED) or not runtime_active("events"):
            continue
        mode = global_target if target == "account" else tenant_target
        for method in methods:
            result.append((name, (method,), read if method in {"GET", "HEAD"} else write,
                           mode, False, False))
    return tuple(result)
