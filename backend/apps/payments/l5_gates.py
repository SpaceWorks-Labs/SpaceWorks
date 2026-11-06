"""Shared lookups for the lane L5 staff routes: a servable space the actor may act in, and
the per-space capability switch (off answers 404, data kept -- #95)."""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_queryset


def require_capability(space, key):
    if not feature_enabled(space, key):
        raise NotFound({"detail": gettext("This feature is turned off for this space."), "code": "feature_disabled"})
    return space


def action_space(request, makerspace_id, action, feature=None):
    """The servable space when the actor holds `action` there (404 otherwise)."""
    space = get_object_or_404(rbac.scope_by_action(request.user, action, servable_queryset(), field="pk"),
                              pk=makerspace_id)
    return require_capability(space, feature) if feature else space


def finance_space(request, makerspace_id, feature="finance.ledger"):
    """The servable space plus the actor's finance view; 404 without any finance area."""
    from apps.payments.finance_scope import finance_view

    space = get_object_or_404(servable_queryset(), pk=makerspace_id)
    view = finance_view(request.user, space.pk)
    if not view.any:
        raise NotFound()
    if feature:
        require_capability(space, feature)
    return space, view
