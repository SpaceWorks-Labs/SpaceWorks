"""Audit presentation for per-space backup and restore (owner decisions #110d, #111 Q5/Q15).

Rows are written in the restored space, so its managers see every step. Leaves are
counts, codes, stages and archive ids: never row contents, names or object keys.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("backup.space_restore_requested", gettext_lazy("Space restore requested"), ("restore_id", "archive_id", "source")),
    P("backup.space_restore_preview_ready", gettext_lazy("Space restore preview ready"),
      ("restore_id", "removed_rows", "added_rows", "blocking_count", "money_after_restore_point")),
    P("backup.space_restore_confirmed", gettext_lazy("Space restore confirmed"), ("restore_id", "archive_id")),
    P("backup.space_restore_completed", gettext_lazy("Space restore completed"),
      ("restore_id", "archive_id", "safety_archive_id", "removed_rows", "restored_rows", "money_after_restore_point",
       "objects_restored")),
    P("backup.space_restore_failed", gettext_lazy("Space restore failed"), ("restore_id", "stage", "error_code")),
    P("backup.space_restore_point_extracted", gettext_lazy("Space restore point extracted from a whole-platform backup"),
      ("archive_id", "source_archive_id", "size_bytes")),
    P("backup.space_restore_aborted", gettext_lazy("Space restore cancelled"), ("restore_id", "stage")),
)
