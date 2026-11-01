"""Release-2 lane L11: key rotation, re-encryption, drills, notices, moves and station credentials.

Leaves are kinds, states, counts, fingerprints, digests and codes: never a key, a
recipient, a file path or a note.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("backup.platform_key_rotated", "Backup key rotation recorded",
      ("kind", "new_fingerprint", "retired_count", "stale_archives")),
    P("backup.reencrypted", "Backup archive re-encrypted to the current keys", ("scope", "size_bytes")),
    P("backup.purged", "Backup archive purged", ("scope", "row_kept_for_restore_history")),
    P("backup.reencrypt_requested", "Background re-encryption started"),
    P("backup.reencrypt_cancelled", "Background re-encryption stopped"),
    P("backup.drill_completed", "Restore drill passed", ("rows", "objects_verified")),
    P("backup.drill_failed", "Restore drill failed", ("rows", "error_code")),
    P("backup.operator_notice_sent", "Archive-ready notice sent", ("notice", "scope", "recipients")),
    P("station_credentials.revoked_on_restore", "Station credentials revoked after a restore",
      ("scope", "revoked")),
    P("selfhost_move.requested", "Move to own server requested", ("status",)),
    P("selfhost_move.approved", "Move to own server approved", ("status",)),
    P("selfhost_move.rejected", "Move to own server declined", ("status",)),
    P("selfhost_move.export_started", "Move export started", ("status", "recipient_fingerprint")),
    P("selfhost_move.exported", "Move export finished", ("status", "artifact_sha256")),
    P("selfhost_move.export_failed", "Move export failed", ("status", "failure_code")),
    P("selfhost_move.downloaded", "Move export downloaded", ("status", "artifact_sha256")),
    P("selfhost_move.artifact_discarded", "Move export file deleted", ("status",)),
    P("selfhost_move.imported", "Space imported from a move", ("status", "source_archive_digest", "people")),
)
