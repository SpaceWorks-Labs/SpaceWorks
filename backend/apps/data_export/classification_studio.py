"""Card Studio (decision 314/315): space card and certificate templates travel with the space.

A template is the space's own saved design (a version 3 document that may name the space's uploaded design assets,
exactly like a `CardDesign`). It carries no user FK and no design FK: the author is in the audit row and
`source_design_id` is a plain reference.
"""
from .types import TenantPredicate as P

FIELDS = {
    "card_designs.CardTemplate": "id makerspace name description kind domain_hint stock theme document source_design_id "
                                 "created_at updated_at",
}
DATASETS = {"card_designs.CardTemplate": ("cards/templates.csv", P(("makerspace",)))}
NON_REFERENCE_JSON_FIELDS = frozenset({("card_designs.CardTemplate", "document")})
