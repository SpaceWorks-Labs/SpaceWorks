"""Account-merge dispositions for lane r2-submit-content (stage shortlists #179, deadline extensions #180 S2)."""

from .merge_registry_types import KEEP_ON_SHELL as K

_HISTORY = "Append-only attribution of a staff decision; stays with the account that acted."

ROWS = (
    (K, "events.StageShortlist", "created_by", _HISTORY),
    (K, "events.StageShortlistAnnouncement", "published_by", _HISTORY),
    (K, "events.StageExtension", "created_by", _HISTORY),
)
