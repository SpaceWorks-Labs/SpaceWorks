"""Parity O-B1 (member units): tenant-dump field snapshot, authority and uniqueness.

The unit tree, assignments, staff scopes and plan limits travel with the space (data_export
`classification_r3_org_units`); foreign keys remap like any other. A unit's `path` is a path of codes, so it is
copied as is. A staff unit scope only narrows what the target's own role already grants and is inert while the
target's `membership.unit_scoped_staff` switch is off; unit codes and slugs are unique per space, which the
guard treats as tenant-owned.
"""
from apps.data_export.classification_r3_org_units import FIELDS as _FIELDS

FIELD_NAMES = {label: frozenset(names.split()) for label, names in _FIELDS.items()}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    keep = disposition.PRESERVE

    def same(label, names, reason):
        return tuple(((label, name), authority(keep, reason)) for name in names.split())

    return (
        *same("makerspaces.MemberUnitSettings", "level_names", "The space's own level names."),
        *same("makerspaces.MemberUnit", "name slug code level path sort_order payment_instructions archived_at",
              "The unit tree is the space's own organisation of its members."),
        *same("makerspaces.ImportedMemberUnit", "review_status reviewed_at",
              "A pending review stays pending on the target; it sends nothing until a lead approves it there."),
    )


def unique_rules(remap, policy):
    """None: unit code, unit slug and plan/unit pairs are all scoped by the space."""
    return {}
