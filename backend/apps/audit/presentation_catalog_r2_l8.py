"""Release-2 lane L8: row-level security and per-space key lifecycle (#75d, #120, #128 C-25/C-26).

Leaves are versions, counts, codes and capability/table names: never key material, salts,
browser key values or row contents. Key-job rows are written in the space, so its managers
see every rotation and re-key; RLS rows are platform rows.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

_JOB = ("job_id", "from_version", "to_version")
_DONE = ("job_id", "to_version", "rows", "skipped", "retained_versions")

ENTRIES = (
    P("encryption.key_rotated", gettext_noop("Encryption key rotated"), _JOB),
    P("encryption.key_rotation_completed", gettext_noop("Encryption key rotation finished"), _DONE),
    P("encryption.emergency_rekey_started", gettext_noop("Emergency re-key started"), _JOB),
    P("encryption.emergency_rekey_completed", gettext_noop("Emergency re-key finished"), _DONE),
    P("encryption.search_key_rotation_started", gettext_noop("Search key rotation started"), ("job_id", "to_version")),
    P("encryption.search_reindexed", gettext_noop("Search index rebuilt under a new key"), ("job_id", "to_version", "rows")),
    P("encryption.key_job_failed", gettext_noop("Key job stopped"), ("job_id", "kind", "error")),
    P("makerspace.public_api_key_rotated", gettext_noop("Public site browser key rotated"),
      ("previous_fingerprint", "current_fingerprint", "previous_valid_until")),
    P("rls.capability_used", gettext_noop("Cross-space capability used"), ("capability", "path", "actor_kind")),
    P("rls.report_only_violation", gettext_noop("Cross-space row reported (RLS report-only)"), ("table", "path")),
)
