"""Shared lookups for the L4 staff routes: rbac-scoped, switch-gated, 404 when off.

A makerspace route resolves the space through `_makerspace` (visibility, then the action,
403 when visible but not allowed); a membership route scopes the row through
`rbac.scope_by_action`, so another space's row is 404, never 403. Both then require the
route's `membership.*` switch (404 when off, #95).
"""
from django.shortcuts import get_object_or_404

from apps.accounts import rbac
from apps.admin_api.views_member_memberships import _makerspace
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import MakerspaceMembership

MANAGE = rbac.Action.MANAGE_MEMBERS


def staff_space(actor, makerspace_id, feature, action=MANAGE):
    return require_membership_feature(_makerspace(actor, makerspace_id, action), feature)


def staff_membership(actor, pk, feature, action=MANAGE):
    membership = get_object_or_404(
        rbac.scope_by_action(actor, action, MakerspaceMembership.objects.select_related("makerspace", "user")),
        pk=pk)
    require_membership_feature(membership.makerspace, feature)
    return membership


def scoped_row(actor, queryset, pk, feature, action=MANAGE):
    row = get_object_or_404(rbac.scope_by_action(actor, action, queryset.select_related("makerspace")), pk=pk)
    require_membership_feature(row.makerspace, feature)
    return row
