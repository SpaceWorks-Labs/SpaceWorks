"""Staff routes refuse an outsider without revealing whether the makerspace exists (decision 481(1)).

A staff route names its makerspace in the path. Its view checks the module gate
(`require_module`, which looks the space up) and the per-action RBAC in the order it was
written, so an actor with no standing in the space used to get 403 for a real space and
404 for a missing one: an existence oracle. Standing is decided first, here, at the one
place every refusal passes through (the project exception handler): when a staff route
refuses an actor who holds no membership, organization grant or resource grant in the
path's makerspace, the answer is the same not-found a missing space gets, whatever the
view said (403, `module_disabled`, a lookup 404, a validation 400).

Actors with standing keep the real answer: `module_disabled` for an off module and the
403 for an action they lack. Platform superadmins are untouched. Answers that do not
depend on the id at all (401 authentication, 405 method, 429 throttle) are kept.

The JWT authenticator's route-class gate (`surface_policy.enforce_request`) already
refuses an outsider uniformly before any view runs; this keeps the view layer itself
from being an oracle for every other way a request reaches it.
"""
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.accounts import rbac
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
from apps.accounts.models import User

STAFF_PREFIXES = ("/api/v1/admin/", "/api/v1/procurement/", "/api/v1/guest-admin/")
_PATH_KWARGS = ("makerspace_id", "makerspace_pk")
_ID_INDEPENDENT = frozenset({401, 405, 429})


def has_standing(actor, makerspace_id):
    """The actor belongs to, staffs, or holds an organization or resource grant in this space."""
    scope = rbac.resolve_scope(actor)
    if scope is rbac.ALL or makerspace_id in scope:
        return True
    if rbac.effective_actions(actor, makerspace_id):
        return True
    from apps.makerspaces.resource_grant_sources import has_authority
    return has_authority(actor, makerspace_ids=[makerspace_id])


def not_found_response():
    return Response({"detail": NotFound.default_detail, "code": NotFound.default_code},
                    status=status.HTTP_404_NOT_FOUND)


def outsider_refusal(response, context):
    """Replace a staff route's refusal with the missing-space answer when the actor has no standing."""
    if response is None or not 400 <= response.status_code < 500 or response.status_code in _ID_INDEPENDENT:
        return response
    request = (context or {}).get("request")
    # The actor DRF already authenticated, if any: reading `request.user` here would run the
    # authenticators from the error path when the refusal came before authentication.
    actor = getattr(request, "_user", None)
    if not getattr(actor, "is_authenticated", False) or actor.is_superuser or actor.role == User.Role.SUPERADMIN:
        return response
    makerspace_id = _path_makerspace_id(request, (context or {}).get("view"))
    if makerspace_id is None or not _staff_route(request) or has_standing(actor, makerspace_id):
        return response
    return not_found_response()


def _staff_route(request):
    match = getattr(request, "resolver_match", None)
    if route_class(getattr(match, "url_name", None)) in {DELEGABLE, MEMBERSHIP_ONLY}:
        return True
    return getattr(request, "path", "").startswith(STAFF_PREFIXES)


def _path_makerspace_id(request, view):
    kwargs = dict(getattr(getattr(request, "resolver_match", None), "kwargs", None) or {})
    kwargs.update(getattr(view, "kwargs", None) or {})
    for key in _PATH_KWARGS:
        try:
            value = int(kwargs[key])
        except (KeyError, TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None
