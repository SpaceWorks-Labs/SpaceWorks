"""Release 2 L11: source-gate declarations for restore drills, re-encryption and the move export."""


def gate_tasks(exemptions):
    exemptions.update({
        "apps.backup.tasks.run_restore_drill_task": (
            "Restore drill: reads one archive into a throwaway scratch database it drops; writes only "
            "its platform drill report (OMITTED), never a tenant row."
        ),
        "apps.backup.tasks.reencrypt_archives_task": (
            "Platform backup control plane: rewrites archive bytes and BackupArchive rows (OMITTED); "
            "no tenant writes."
        ),
        "apps.tenant_migration.tasks.run_selfhost_move_export_task": (
            "Self-host move export: claims the space's own source gate (quiesced_snapshot) before it "
            "reads, so it IS the gate owner rather than a gated writer."
        ),
    })
