"""Release-2 lane L11: key rotation, re-encryption, drills, notices, moves and station credentials.

Leaves are kinds, states, counts, fingerprints, digests and codes: never a key, a
recipient, a file path or a note.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("backup.platform_key_rotated", gettext_noop("Backup key rotation recorded"),
      ("kind", "new_fingerprint", "retired_count", "stale_archives")),
    P("backup.reencrypted", gettext_noop("Backup archive re-encrypted to the current keys"), ("scope", "size_bytes")),
    P("backup.purged", gettext_noop("Backup archive purged"), ("scope", "row_kept_for_restore_history")),
    P("backup.reencrypt_requested", gettext_noop("Background re-encryption started")),
    P("backup.reencrypt_cancelled", gettext_noop("Background re-encryption stopped")),
    P("backup.drill_completed", gettext_noop("Restore drill passed"), ("rows", "objects_verified")),
    P("backup.drill_failed", gettext_noop("Restore drill failed"), ("rows", "error_code")),
    P("backup.operator_notice_sent", gettext_noop("Archive-ready notice sent"), ("notice", "scope", "recipients")),
    P("station_credentials.revoked_on_restore", gettext_noop("Station credentials revoked after a restore"),
      ("scope", "revoked")),
    P("selfhost_move.requested", gettext_noop("Move to own server requested"), ("status",)),
    P("selfhost_move.approved", gettext_noop("Move to own server approved"), ("status",)),
    P("selfhost_move.rejected", gettext_noop("Move to own server declined"), ("status",)),
    P("selfhost_move.export_started", gettext_noop("Move export started"), ("status", "recipient_fingerprint")),
    P("selfhost_move.exported", gettext_noop("Move export finished"), ("status", "artifact_sha256")),
    P("selfhost_move.export_failed", gettext_noop("Move export failed"), ("status", "failure_code")),
    P("selfhost_move.downloaded", gettext_noop("Move export downloaded"), ("status", "artifact_sha256")),
    P("selfhost_move.artifact_discarded", gettext_noop("Move export file deleted"), ("status",)),
    P("selfhost_move.imported", gettext_noop("Space imported from a move"), ("status", "source_archive_digest", "people")),
)
