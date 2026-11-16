"""Release-2 lane L11: tenant-dump field snapshot of the backup follow-up models.

All three are OMITTED from exports (data_export `classification_r2_l11`): two kinds of
deployment backup state and platform move coordination. `backup.PlatformBackupSettings`
gains three platform fields (drill cadence, the operator notice switch and a pending
re-encryption request).
"""

FIELD_NAMES = {
    "backup.BackupKeyFingerprint": frozenset("id kind fingerprint first_seen_at retired_at retired_by".split()),
    "backup.RestoreDrillReport": frozenset(
        "id makerspace makerspace_id_snapshot archive archive_id_snapshot started_at finished_at outcome "
        "error_code error_detail checks".split()),
    "tenant_migration.SelfHostMoveRequest": frozenset(
        "id makerspace status note requested_by requested_at decided_by decided_at decision_note "
        "recipient_fingerprint artifact_path artifact_sha256 exported_at failure_code updated_at".split()),
}
EXTRA_FIELDS = {
    "backup.PlatformBackupSettings": frozenset(
        {"restore_drill_interval_days", "archive_ready_notice_enabled", "reencrypt_requested_at"}),
}
