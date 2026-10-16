"""Delegates may name themselves and this space's valid Machine Managers."""

from django.db.models import Q

from apps.accounts.rbac_roles import role_slug_filter
from apps.admin_api.recipient_rule_common import memberships_for
from apps.makerspaces.models import MakerspaceRole


def delegated_identities(makerspace, actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        return frozenset(), frozenset()
    roles = frozenset(MakerspaceRole.objects.filter(
        makerspace=makerspace, slug="machine_manager",
    ).values_list("pk", flat=True))
    users = frozenset(memberships_for(makerspace).filter(
        Q(user_id=actor.pk) | role_slug_filter("machine_manager"),
    ).values_list("user_id", flat=True))
    return roles, users
