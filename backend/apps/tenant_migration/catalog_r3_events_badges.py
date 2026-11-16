"""Parity E-B2 tenant-dump field snapshot: see ``data_export.classification_r3_events_badges`` for the reasons.

Badge print receipts travel with their event as append-only history; the card role lock travels with the card.
"""

FIELD_NAMES = {
    "events.EventBadgePrint": frozenset("id makerspace event registration card actor method stock role operation_id "
                                        "printed_at reported_at".split()),
}
EXTRA_FIELDS = {"events.EventIdCard": frozenset({"role_locked"})}
PROJECTED_LABELS = frozenset(FIELD_NAMES)
