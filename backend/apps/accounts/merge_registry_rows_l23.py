"""Account-merge dispositions for lane L23 (metered machine sessions, release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K

_HISTORY = "Immutable session history (DB-guarded once closed); actor_ids_for follows the alias."

ROWS = (
    (K, "machines.MachineSession", "member started_by stopped_by", _HISTORY),
    (K, "machines.MachineSessionAmendment", "member actor", "Append-only staff decision (DB-guarded)."),
)
