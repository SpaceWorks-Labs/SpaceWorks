"""Parity O-B1: unit scope -- narrowing a STAFF member's local membership authority to one unit's subtree.

Unit scope is NOT an RBAC action. It never grants anything; it only removes rows from what a
`MakerspaceMembership`-derived staff role could already see or change. It is applied AFTER
`rbac.scope_by_action`, which stays the tenancy boundary (cross-tenant is 404 there).

Who is never narrowed (`unit_paths_for` returns None, "the whole space"):
* a superadmin;
* an actor whose authority for the action comes from an ORGANIZATION grant (grants confer actions across
  the space; `INVARIANTS.md` org-derived authority) -- pass `action` so a local scope is not lifted by an
  unrelated org grant;
* staff with no `StaffUnitScope` row;
* any space with `membership.units` or `membership.unit_scoped_staff` off (switch off = no narrowing).

Consumers:
* `unit_paths_for(actor, makerspace_id, action=None)` -> None | list[str] of path prefixes ("/3/9/").
* `narrow_memberships(queryset, actor, makerspace_id, action=None)` -> `MakerspaceMembership` queryset limited
  to members whose unit lies in the prefixes (members with no unit are hidden from a scoped actor).
* `narrow_by_unit_lookup(queryset, actor, makerspace_id, lookup, action=None)` -> any queryset, `lookup` being
  the path to the member's unit path, e.g. `"unit_choice__unit__path"` on a `MembershipRequest`.
* `member_in_scope(actor, membership, action=None)` -> bool.
* `allowed_member_ids(actor, makerspace_id, action=None)` -> None (everyone) | set of membership ids.
* `require_member_in_scope(actor, membership, action=None)` -> raises Http404 (an out-of-scope member does not
  exist for this actor, exactly like a cross-tenant row).
* `require_request_in_scope(actor, request_row, action=None)` -> Http404 unless the join request's unit is in scope.
* `require_space_wide(actor, makerspace_id, action=None)` -> raises `unit_scope_forbids` (403) for space-wide
  settings.
* `unit_in_scope(actor, makerspace_id, unit, action=None)` -> bool: may this actor place a member in `unit`.
"""
from django.db.models import Q
from django.http import Http404
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.models_member_units import StaffUnitScope

MEMBER_UNIT_LOOKUP = "unit_assignment__unit__path"


def _org_confers(actor, makerspace_id, action):
    from apps.accounts.rbac_organizations import _org_actions_for
    granted = rbac.expand_implied_actions(_org_actions_for(actor, makerspace_id))
    return bool(granted) if action is None else action in granted


def unit_paths_for(actor, makerspace_id, action=None):
    """None = the whole space; otherwise the list of subtree prefixes the actor is confined to."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return None
    if actor.is_superuser or actor.role == actor.Role.SUPERADMIN:
        return None
    scopes = list(StaffUnitScope.objects.filter(
        makerspace_id=makerspace_id, membership__user=actor, membership__status="active",
    ).select_related("unit"))
    if not scopes:
        return None
    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None or not (membership_feature_on(space, "units") and membership_feature_on(space, "unit_scoped_staff")):
        return None
    if _org_confers(actor, makerspace_id, action):
        return None
    return sorted({row.unit.path for row in scopes})


def _prefix_q(lookup, prefixes):
    query = Q()
    for prefix in prefixes:
        query |= Q(**{f"{lookup}__startswith": prefix})
    return query


def narrow_by_unit_lookup(queryset, actor, makerspace_id, lookup, action=None):
    prefixes = unit_paths_for(actor, makerspace_id, action)
    if prefixes is None:
        return queryset
    return queryset.filter(_prefix_q(lookup, prefixes))


def narrow_memberships(queryset, actor, makerspace_id, action=None):
    return narrow_by_unit_lookup(queryset, actor, makerspace_id, MEMBER_UNIT_LOOKUP, action)


def member_in_scope(actor, membership, action=None):
    prefixes = unit_paths_for(actor, membership.makerspace_id, action)
    if prefixes is None:
        return True
    return MakerspaceMembership.all_tracks.filter(pk=membership.pk).filter(
        _prefix_q(MEMBER_UNIT_LOOKUP, prefixes)).exists()


def require_member_in_scope(actor, membership, action=None):
    if not member_in_scope(actor, membership, action):
        raise Http404()


def unit_in_scope(actor, makerspace_id, unit, action=None):
    prefixes = unit_paths_for(actor, makerspace_id, action)
    return prefixes is None or any(unit.path.startswith(prefix) for prefix in prefixes)


def require_space_wide(actor, makerspace_id, action=None):
    """Refuse a space-wide setting to a unit-scoped actor (typed `unit_scope_forbids`)."""
    if unit_paths_for(actor, makerspace_id, action) is not None:
        error = PermissionDenied(gettext("A unit-scoped role cannot change space-wide settings."))
        error.detail = {"code": "unit_scope_forbids", "detail": str(error.detail)}
        raise error


def require_request_in_scope(actor, request_row, action=None):
    """A join request is in scope through the unit its applicant chose (no unit: hidden from a scoped actor)."""
    prefixes = unit_paths_for(actor, request_row.makerspace_id, action)
    if prefixes is None:
        return
    if not narrow_by_unit_lookup(type(request_row).objects.filter(pk=request_row.pk), actor,
                                 request_row.makerspace_id, "unit_choice__unit__path", action).exists():
        raise Http404()


def allowed_member_ids(actor, makerspace_id, action=None):
    """None = every member of the space; otherwise the set of community membership ids in the actor's scope."""
    if unit_paths_for(actor, makerspace_id, action) is None:
        return None
    return set(narrow_memberships(MakerspaceMembership.objects.filter(makerspace_id=makerspace_id), actor,
                                  makerspace_id, action).values_list("pk", flat=True))
