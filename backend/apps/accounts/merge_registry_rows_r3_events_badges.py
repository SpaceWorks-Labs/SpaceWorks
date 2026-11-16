"""Account-merge dispositions for parity E-B2 (badge print receipts)."""

from .merge_registry_types import KEEP_ON_SHELL as K

_HISTORY = "Append-only attribution of the staff member who reported a print; stays with the account that acted."

ROWS = (
    (K, "events.EventBadgePrint", "actor", _HISTORY),
)
