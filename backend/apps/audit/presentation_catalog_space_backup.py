"""Audit presentation for per-space backup and restore (owner decisions #110d, #111 Q5/Q15).

Rows are written in the restored space, so its managers see every step. Leaves are
counts, codes, stages and archive ids: never row contents, names or object keys.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("backup.space_restore_requested", "Space restore requested", ("archive_id", "source")),
    P("backup.space_restore_preview_ready", "Space restore preview ready",
      ("removed_rows", "added_rows", "blocking_count", "money_after_restore_point")),
    P("backup.space_restore_confirmed", "Space restore confirmed", ("archive_id",)),
    P("backup.space_restore_completed", "Space restore completed",
      ("archive_id", "safety_archive_id", "removed_rows", "restored_rows", "money_after_restore_point",
       "objects_restored")),
    P("backup.space_restore_failed", "Space restore failed", ("stage", "error_code")),
    P("backup.space_restore_aborted", "Space restore cancelled", ("stage",)),
)
