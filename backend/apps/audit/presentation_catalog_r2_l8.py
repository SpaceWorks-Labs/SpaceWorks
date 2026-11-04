"""Release-2 lane L8: row-level security and per-space key lifecycle (#75d, #120, #128 C-25/C-26).

Leaves are versions, counts, codes and capability/table names: never key material, salts,
browser key values or row contents. Key-job rows are written in the space, so its managers
see every rotation and re-key; RLS rows are platform rows.
"""

from .presentation_catalog_types import P

_JOB = ("job_id", "from_version", "to_version")
_DONE = ("job_id", "to_version", "rows", "skipped", "retained_versions")

ENTRIES = (
    P("encryption.key_rotated", "Encryption key rotated", _JOB),
    P("encryption.key_rotation_completed", "Encryption key rotation finished", _DONE),
    P("encryption.emergency_rekey_started", "Emergency re-key started", _JOB),
    P("encryption.emergency_rekey_completed", "Emergency re-key finished", _DONE),
    P("encryption.search_key_rotation_started", "Search key rotation started", ("job_id", "to_version")),
    P("encryption.search_reindexed", "Search index rebuilt under a new key", ("job_id", "to_version", "rows")),
    P("encryption.key_job_failed", "Key job stopped", ("job_id", "kind", "error")),
    P("makerspace.public_api_key_rotated", "Public site browser key rotated",
      ("previous_fingerprint", "current_fingerprint", "previous_valid_until")),
    P("rls.capability_used", "Cross-space capability used", ("capability", "path", "actor_kind")),
    P("rls.report_only_violation", "Cross-space row reported (RLS report-only)", ("table", "path")),
)
