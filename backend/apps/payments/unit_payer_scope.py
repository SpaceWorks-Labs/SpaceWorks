"""Unit scope for money (parity O-B3 over O-B1): a unit-scoped staff member sees and records only the charges
of members inside their unit's subtree.

`payer_user_ids` returns None when the actor is not narrowed (superadmin, organisation grant, no scope row, or
the unit switches off -- all decided in `member_unit_scope.unit_paths_for`), otherwise the set of user ids of
the community members in scope. A charge with no member behind it (a guest or anonymous payer) belongs to no
unit, so a scoped actor never sees it, the same way members without a unit are hidden from them. Out of scope
reads as "not found": the row does not exist for this actor.
"""


def payer_user_ids(actor, makerspace_id, action):
    from apps.makerspaces.member_unit_scope import allowed_member_ids
    from apps.makerspaces.models import MakerspaceMembership

    ids = allowed_member_ids(actor, makerspace_id, action)
    if ids is None:
        return None
    return set(MakerspaceMembership.objects.filter(pk__in=ids).values_list("user_id", flat=True))


def narrow_payments(queryset, actor, makerspace_id, action):
    payers = payer_user_ids(actor, makerspace_id, action)
    return queryset if payers is None else queryset.filter(member_id__in=payers)
