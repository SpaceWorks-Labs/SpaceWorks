"""Separate tenant authority, platform visibility and anonymous service metering.

Platform views mint the context after their superadmin permission check. Builders
must call require_platform_context too, including when called outside the registry.
This capability is server-owned; no request/filter dictionary can supply it.
"""

from django.utils.translation import gettext
from dataclasses import dataclass

from rest_framework.exceptions import PermissionDenied

_VIEW_TOKEN = object()


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
        raise PermissionDenied(gettext("Active superadmin platform authority required."))


def _platform_context_for_view(request):
    """Private view factory; never call from a tenant/org builder or serializer."""
    return PlatformContext(request.user, _view_token=_VIEW_TOKEN)


def require_platform_context(ctx):
    if not isinstance(ctx, PlatformContext):
        raise PermissionDenied(gettext("Platform context required."))
    _require_active_superadmin(ctx.actor)
    return ctx


def platform_analytics_spaces(ctx):
    from .platform_dashboard import platform_spaces
    require_platform_context(ctx)
    return platform_spaces()

