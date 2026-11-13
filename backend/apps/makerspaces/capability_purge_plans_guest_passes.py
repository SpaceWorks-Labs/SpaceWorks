"""Capability purge plan for decision 223: `membership.guest_passes` (superadmin-only, previewed, audited).

Deletes every guest pass, day-pass product and the guest policy of the space. The `Payment`
rows a day pass raised are ledger money and stay; accounts, memberships and waivers stay.
"""


def _delete(space, cursor):
    from .guest_pass_purge import module_delete
    from .module_purge_collectors_single_model import _counts
    count, labels = module_delete(space)
    return _counts(model_labels=labels, guest_passes=count)


def _preview(space):
    from .guest_pass_purge import preview
    return preview(space)


def plans(plan):
    return (
        plan("membership.guest_passes", "Guest passes, day-pass products and the guest policy. Charges already "
             "raised stay in the payment ledger; accounts and memberships stay.", _delete, _preview),
    )
