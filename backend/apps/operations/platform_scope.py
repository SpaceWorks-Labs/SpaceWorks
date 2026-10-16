"""Separate tenant authority, platform visibility and anonymous service metering.

Platform views mint the context after their superadmin permission check. Builders
must call require_platform_context too, including when called outside the registry.
This capability is server-owned; no request/filter dictionary can supply it.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date

from rest_framework.exceptions import PermissionDenied

from apps.accounts.rbac_superadmin import superadmin_hidden_block_applies

_VIEW_TOKEN = object()
PLATFORM_SERVICES = frozenset({"email", "push", "sms", "attestation", "connect", "backups"})


@dataclass(frozen=True, init=False)
class PlatformContext:
    actor: object

    def __init__(self, actor, *, _view_token=None):
        if _view_token is not _VIEW_TOKEN:
            raise TypeError("Only superadmin platform views may construct PlatformContext.")
        _require_active_superadmin(actor)
        object.__setattr__(self, "actor", actor)


def _require_active_superadmin(actor):
    from apps.admin_api.permissions import active_user
    from apps.accounts.rbac_superadmin import _is_superadmin
    from apps.accounts.native_session import is_native_session

    if not active_user(actor) or not _is_superadmin(actor) or is_native_session(actor):
        raise PermissionDenied("Active superadmin platform authority required.")


def _platform_context_for_view(request):
    """Private view factory; never call from a tenant/org builder or serializer."""
    return PlatformContext(request.user, _view_token=_VIEW_TOKEN)


def require_platform_context(ctx):
    if not isinstance(ctx, PlatformContext):
        raise PermissionDenied("Platform context required.")
    _require_active_superadmin(ctx.actor)
    return ctx


def tenant_local_hidden_block_applies(actor, makerspace, action):
    return superadmin_hidden_block_applies(actor, getattr(makerspace, "pk", makerspace), action)


def platform_analytics_spaces(ctx):
    from .platform_dashboard import platform_spaces
    return platform_spaces(require_platform_context(ctx).actor)


def hidden_platform_service_bucket(ctx, rows, *, report_key):
    """Platform-services ONLY: one count per service/day across all hidden tenants.

    Input is an internal count projection: makerspace_id, provider_source,
    service, day (date), count. Own-provider and visible-space rows are ignored.
    Output never includes tenant ids/names, outcomes or any further breakdown.
    Caller must query only the report's requested window before passing rows.
    """
    require_platform_context(ctx)
    if report_key != "platform-services":
        raise PermissionDenied("Hidden buckets are restricted to platform-service usage.")
    from apps.makerspaces.models import Makerspace
    hidden = set(Makerspace.objects.filter(superadmin_access_enabled=False).values_list("pk", flat=True))
    counts = Counter()
    for row in rows:
        if row.get("provider_source") != "platform" or row.get("makerspace_id") not in hidden:
            continue
        service, day, count = row.get("service"), row.get("day"), row.get("count")
        if service not in PLATFORM_SERVICES or type(day) is not date:
            raise ValueError("Hidden usage requires an allowlisted service and calendar date.")
        if type(count) is not int or count < 0:
            raise ValueError("Hidden usage count must be a nonnegative integer.")
        counts[(service, day)] += count
    return [{"service": service, "day": day.isoformat(), "bucket": "hidden_makerspaces", "count": count}
            for (service, day), count in sorted(counts.items())]
