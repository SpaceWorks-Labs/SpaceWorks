"""Parity O-B4 part 2 (staff ID cards): tenant-dump field snapshot and uniqueness.

Staff cards and the staff number scheme travel with the space (data_export `classification_r3_org_b4`); their
foreign keys remap like any other. Uniqueness is per space / per remapped membership, so it follows the imported
parent. Check tokens and wallet passes never travel; a moved space mints fresh links on first use.
"""
from apps.data_export.classification_r3_org_b4 import FIELDS as _FIELDS

FIELD_NAMES = {label: frozenset(names.split()) for label, names in _FIELDS.items()}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def unique_rules(remap, policy):
    follow = "Unique per space or per remapped membership; follows the imported parent."
    return {("card_designs.StaffCard", name): policy(remap, follow) for name in (
        "uniq_staff_card_number", "uniq_live_staff_card_per_membership", "uniq_staff_card_number_text")}
