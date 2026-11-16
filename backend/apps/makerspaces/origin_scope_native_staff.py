"""Native `X-Makerspace-Id` on staff routes whose owner is looked up only for a native header (MOB-STAFF).

Routes in `NATIVE_ONLY_LOOKUPS` (see `origin_scope_routes_mobstaff`) have a nullable owner: the web resolver must keep
treating a global row as "no target" (the platform superadmin reaches it), so only `validate_native_makerspace_scope`
reads this, like `origin_scope_native_slug`. It adds no tenant-RLS binding, source-gate target or staff-origin target.
"""

from django.apps import apps


def native_staff_targets(request):
    """``(targets, invalid)`` for a native-only route, or ``None`` when the route is not one."""
    match = getattr(request, "resolver_match", None)
    name = getattr(match, "url_name", "") or ""
    from .origin_scope_routes_mobstaff import NATIVE_ONLY_LOOKUPS
    if name not in NATIVE_ONLY_LOOKUPS:
        return None
    label, field = NATIVE_ONLY_LOOKUPS[name]
    pk = (getattr(match, "kwargs", None) or {}).get("pk")
    owner = apps.get_model(label).objects.filter(pk=pk).values_list(field, flat=True).first() if pk is not None else None
    return ({owner}, False) if owner is not None else (set(), True)
