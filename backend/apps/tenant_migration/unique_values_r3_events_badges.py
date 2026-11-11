"""Deployment-global uniqueness for parity E-B2's badge print receipts.

The rule is scoped to a remapped parent (the event), so it follows the imported event. Nothing here is a bearer value.
"""

from .unique_values_policy import REMAP, _policy

RULES = {
    ("events.EventBadgePrint", "event_badge_print_operation"): _policy(
        REMAP, "Unique per remapped event; follows the imported event."),
}
