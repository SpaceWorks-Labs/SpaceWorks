"""Parity E-B2 export classification: badge print receipts and the card role lock.

`events.EventBadgePrint` is the append-only receipt that one badge was printed (desk, station, offline desk or a
bulk job). It holds only ids, the stock and the role: no name, photo, answer or credential, so it exports with the
space like the other event history. `operation_id` is an idempotency key and authenticates nothing.
`events.EventIdCard.role_locked` records that staff set a card's role by hand, so a later reconcile keeps it.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "events.EventBadgePrint": "id makerspace event registration card actor method stock role operation_id "
                              "printed_at reported_at",
}
FIELD_ADDITIONS = {"events.EventIdCard": "role_locked"}
NON_CREDENTIAL = {
    ("events.EventBadgePrint", "operation_id"): "Idempotency key of one reported print; authenticates nothing.",
}
DATASET_SPECS = {
    "events.EventBadgePrint": ("events/badge_prints.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({("events.EventBadgePrint", "actor")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
