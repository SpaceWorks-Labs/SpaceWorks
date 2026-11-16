"""Release-2 lane L11 (backup follow-ups): literal export classification.

`backup.BackupKeyFingerprint` and `backup.RestoreDrillReport` are deployment backup
operations state. `tenant_migration.SelfHostMoveRequest` is platform coordination of a
move and travels with nothing (#128 C-23).
"""

OMITTED_MODELS = {
    "backup.BackupKeyFingerprint": "Platform backup key fingerprints; deployment configuration.",
    "backup.RestoreDrillReport": "Platform restore-drill report; deployment operations state.",
    "tenant_migration.SelfHostMoveRequest": "Platform coordination of a self-host move; travels with nothing.",
}
EXCLUDED_USER_EDGE_REASONS = {
    ("backup.BackupKeyFingerprint", "retired_by"): "Platform superadmin attribution; omitted with the row.",
    ("tenant_migration.SelfHostMoveRequest", "requested_by"): "Platform coordination; omitted with the request.",
    ("tenant_migration.SelfHostMoveRequest", "decided_by"): "Platform superadmin decision; omitted with the request.",
}
RELATIONAL_USER_FIELDS = frozenset(EXCLUDED_USER_EDGE_REASONS)
