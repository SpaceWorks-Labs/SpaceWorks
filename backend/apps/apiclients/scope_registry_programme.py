"""Closed programme route policy; session-only staff commands grant no API-key authority."""
from apps.accounts.programme_route_catalog import ROUTES
from apps.separability.registry import runtime_active


SESSION_ONLY = frozenset(name for name, methods, target in ROUTES
    if name.startswith(("events-programme-admin-", "events-programme-tenant-admin-", "events-programme-library-"))
    or name in {"events-programme-series-guests", "admin-platform-insights"})


def definitions(read, write, global_target, tenant_target):
    result = []
    for name, methods, target in ROUTES:
        if name in SESSION_ONLY or (name.startswith("events-programme-") and not runtime_active("events")):
            continue
        mode = global_target if target == "account" else tenant_target
        for method in methods:
            result.append((name, (method,), read if method in {"GET", "HEAD"} else write,
                           mode, False, False))
    return tuple(result)
