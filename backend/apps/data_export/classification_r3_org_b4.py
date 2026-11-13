"""Parity O-B4 part 2 (staff ID cards): literal export classification.

A staff card is the space's own record of an ID it issued to a staff member, so it travels with the space
(number, held roles at issue, print count, revocation). It adds no `accounts.User` FK: the person is the
`membership` row's data subject. The numbering scheme is plain configuration. The public check token and any
wallet pass of a staff card are credential material and never travel (see `classification_l3.OMITTED_MODELS`).
"""
from .types import TenantPredicate as P

FIELDS = {
    "card_designs.StaffCard": "id makerspace membership card_number number_text roles print_count last_printed_at "
                              "issued_at revoked_at revoked_reason created_at updated_at",
    "card_designs.StaffCardNumbering": "id makerspace prefix pattern updated_at",
}
DATASETS = {
    "card_designs.StaffCard": ("cards/staff_cards.csv", P(("makerspace",))),
    "card_designs.StaffCardNumbering": ("cards/staff_card_numbering.csv", P(("makerspace",))),
}
# `roles` holds role slugs ("space_manager", ...): plain labels, no references.
NON_REFERENCE_JSON_FIELDS = frozenset({("card_designs.StaffCard", "roles")})
