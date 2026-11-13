"""Who reaches which analytics surface. All scoping goes through rbac.

* Per space, viewing dashboards needs ``view_analytics`` there (the Space Manager holds it
  through ``manage_makerspace``; an organization grant may carry it). Managing the login,
  the Metabase URL and secret, the dashboards list and the member-details switch is the
  space's own Space Manager or the superadmin (``rbac.is_space_manager_identity``).
* The module switch comes first: with ``analytics`` off every per-space route is a 404.
* The platform connection is the superadmin's alone.
"""

from django.utils.translation import gettext
from dataclasses import dataclass

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import module_enabled

MODULE_KEY = "analytics"


@dataclass(frozen=True)
class Scope:
    makerspace: Makerspace | None

    @property
    def platform(self):
        return self.makerspace is None

    @property
    def label(self):
        return "platform" if self.platform else "space"


def is_superadmin(user):
    from apps.accounts.models import User

    return bool(user and user.is_authenticated and not getattr(user, "is_tenant_dump_stub", False)
                and (user.is_superuser or user.role == User.Role.SUPERADMIN))


def _space(user, makerspace_id):
    makerspace = get_object_or_404(Makerspace, pk=makerspace_id)
    scope = rbac.resolve_scope(user)
    visible = scope is rbac.ALL or makerspace.pk in scope or rbac.can(user, rbac.Action.VIEW_ANALYTICS, makerspace.pk)
    if not visible:
        raise Http404
    if not module_enabled(makerspace, "analytics"):
        # #183B: a space the caller can see answers the typed SurfaceOff body when the module is off.
        from apps.makerspaces.guards import module_off
        raise module_off("analytics")
    return makerspace


def viewer_scope(user, makerspace_id):
    makerspace = _space(user, makerspace_id)
    if not rbac.can(user, rbac.Action.VIEW_ANALYTICS, makerspace.pk):
        raise PermissionDenied(gettext("Viewing analytics needs view_analytics in this space."))
    return Scope(makerspace)


def manager_scope(user, makerspace_id):
    makerspace = _space(user, makerspace_id)
    if not rbac.is_space_manager_identity(user, makerspace.pk):
        raise PermissionDenied(gettext("Only this space's Space Manager or the superadmin manages analytics."))
    return Scope(makerspace)


def can_manage(user, scope):
    if scope.platform:
        return is_superadmin(user)
    return rbac.is_space_manager_identity(user, scope.makerspace.pk)


def platform_scope(user):
    if not is_superadmin(user):
        raise PermissionDenied(gettext("The platform analytics connection is superadmin-only."))
    return Scope(None)
