"""Capability purge plan for parity O-B1: `membership.units` (superadmin-only, previewed, audited).

Deletes the unit tree, every member/staff/plan/request pointer at a unit and the level names. Members, plans,
staff roles and payments stay; unit-scoped staff simply become space-wide again because their scope row goes.
"""


def _delete(space, cursor):
    from .member_unit_purge import module_delete
    from .module_purge_collectors_single_model import _counts
    count, labels = module_delete(space)
    return _counts(model_labels=labels, member_units=count)


def _preview(space):
    from .member_unit_purge import preview
    return preview(space)


def plans(plan):
    return (
        plan("membership.units", "Member units, their assignments and staff unit scopes. Members, plans and "
             "payments stay; scoped staff become space-wide again.", _delete, _preview),
    )
