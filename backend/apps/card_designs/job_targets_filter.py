"""Bulk card jobs from the member register filter (O-B4, parity C11).

`POST .../member-card-jobs` may carry `filter` instead of explicit card ids. It is the SAME contract the
member roster and the register use (`apps.admin_api.member_register_filters`, O-B2: `q` incl. member number,
`chip`, `plan`, `title`, `unit`, `role`, `standing`, `joined_after`/`joined_before`, `staff`, `verified`, `minor`,
`volunteer`, `waiver_needed`, and the membership `status`). Resolution is server side, inside the actor's scope
(including a unit-scoped card manager's unit), and the card ids are frozen when the job is queued
(`jobs.enqueue`); the per-job caps are unchanged.
"""
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext

from apps.accounts import rbac

def clean_filter(raw):
    """The contract of `admin_api.member_register_filters` (O-B2): the same keys the register and roster take."""
    from apps.admin_api.member_register_filters import clean_params
    if not isinstance(raw, dict):
        raise ValidationError({"filter": gettext("Send the filter as an object.")})
    return clean_params(raw)


def resolve(actor, space, raw_filter):
    """-> card ids (live cards of the members the register filter selects, inside the actor's scope)."""
    from apps.admin_api.member_register_filters import apply_member_filters
    from apps.makerspaces.models import MakerspaceMembership, MemberCard
    params = clean_filter(raw_filter)
    members = rbac.scope_by_action(actor, rbac.Action.MANAGE_MEMBER_CARDS,
                                   MakerspaceMembership.objects.filter(makerspace=space))
    # Same contract as the register and roster; unit scope is applied for THIS action (a card manager's own scope).
    members = apply_member_filters(members, params, space, actor=actor, action=rbac.Action.MANAGE_MEMBER_CARDS)
    members = members.filter(status=params.get("status", "active"))
    return list(MemberCard.objects.filter(makerspace=space, revoked_at__isnull=True,
                                          membership__in=members.values("pk"))
                .order_by("card_number").values_list("pk", flat=True).distinct())
