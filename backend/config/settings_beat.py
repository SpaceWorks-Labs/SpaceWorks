"""Base Celery beat schedule and legacy calendar slots."""

from config.settings_runtime import crontab

# Canonical outbox and per-device recovery share the sending cutover fence.
# Deployment activation remains an explicit operator checkpoint after replay.
CELERY_BEAT_SCHEDULE = {
    "missing-payment-bills": {
        "task": "apps.payments.tasks.issue_missing_bills_task",
        "schedule": crontab(minute="*/5"),
    },
    # Rebuilds refund cases an events cancellation hook failed to open; idempotent.
    "rebuild-refund-cases": {
        "task": "apps.payments.tasks.rebuild_refund_cases_task",
        "schedule": crontab(minute="17"),
    },
    "notification-contract-outbox": {
        "task": "apps.integrations.notification_tasks.sweep_notification_outbox",
        "schedule": crontab(minute="*"),
    },
    "messaging-credential-wipe": {"task": "apps.integrations.tasks_messaging_settings.wipe_messaging_credentials_task", "schedule": crontab(hour=2, minute=15)},
    "inventory-stock-snapshot": {"task": "apps.inventory.tasks.snapshot_stock_task", "schedule": crontab(hour=0, minute=15)},
    "member-push-recovery": {
        "task": "apps.notifications.tasks.sweep_member_push",
        "schedule": crontab(minute="*/5"),
    },
    "purge-deleted-accounts": {
        "task": "apps.accounts.tasks.purge_deleted_accounts_task",
        "schedule": crontab(hour=3, minute=20),
    },
    # Superadmin PII windows last 30 minutes (#111 Q12). Reads close lapsed windows
    # lazily; this sweep writes the expiry audit row for windows nobody reads again.
    "pii-access-expiry": {
        "task": "apps.accounts.tasks.expire_pii_access_windows_task",
        "schedule": crontab(minute="*/5"),
    },
    "reminder-sweep": {
        "task": "apps.operations.tasks_reminders.run_reminder_sweep_task",
        "schedule": crontab(minute="*/5"),
    },
    "platform-problem-checks": {
        "task": "apps.operations.tasks_platform.run_platform_problem_checks_task",
        "schedule": crontab(minute="*/15"),
    },
    "membership-admissions": {
        "task": "apps.operations.tasks_admissions.sweep_membership_admissions_task",
        "schedule": crontab(minute="*/5"),
    },
    "scan-offline-devices": {
        "task": "apps.devices.tasks.scan_offline_devices_task",
        "schedule": crontab(minute="*"),
    },
    "adapter-safety-sweep": {
        "task": "apps.devices.tasks.adapter_safety_sweep_task",
        "schedule": crontab(minute="*"),
    },
    "adapter-webhook-sweep": {
        "task": "apps.devices.tasks.adapter_webhook_sweep_task",
        "schedule": crontab(minute="*"),
    },
    "adapter-media-sweep": {
        "task": "apps.devices.tasks.adapter_media_sweep_task",
        "schedule": crontab(minute="*/10"),
    },
    "purge-adapter-recordings": {
        "task": "apps.devices.tasks.purge_adapter_recordings_task",
        "schedule": crontab(hour=3, minute=40),
    },
    "cleanup-kiosk-replay-commands": {
        "task": "apps.hardware_requests.tasks_replay.cleanup_replay_commands_task",
        "schedule": crontab(hour=3, minute=20),
    },
    "flush-api-client-usage": {
        "task": "apps.apiclients.tasks.flush_api_client_usage_task",
        "schedule": crontab(minute="*"),
    },
    "audit-attestation": {
        "task": "apps.audit.tasks.run_audit_attestation_task",
        "schedule": crontab(minute="*/5"),
    },
    # Recovery issuance stays entirely off the anonymous request path. One minute keeps
    # user-visible latency bounded while each invocation still claims a bounded batch.
    "drain-password-reset-envelopes": {
        "task": "apps.accounts.tasks.drain_password_reset_envelopes_task",
        "schedule": crontab(minute="*"),
    },
    "return-reminders": {
        "task": "apps.hardware_requests.tasks.send_return_reminders_task",
        "schedule": crontab(minute=0),
    },
    "evidence-object-expiry": {
        "task": "apps.evidence.tasks.sweep_evidence_retention_task",
        "schedule": crontab(minute=10, hour="*/6"),
    },
    # Every 360 minutes: reconcile due late-write receipts first, then new cleanup.
    "evidence-abandoned-upload-cleanup": {
        "task": "apps.evidence.tasks.cleanup_abandoned_evidence_uploads_task",
        "schedule": crontab(minute=40, hour="*/6"),
    },
    "extend-event-series": {
        "task": "apps.events.tasks.extend_event_series_task",
        "schedule": crontab(minute=10),
    },
    "event-admission-deadlines": {
        "task": "apps.events.tasks_programme.sweep_admission_deadlines_task",
        "schedule": crontab(minute="*/5"),
    },
    "event-contributor-maintenance": {
        "task": "apps.events.tasks_contributions.sweep_contributor_maintenance_task",
        "schedule": crontab(minute="*"),
    },
    "event-scheduled-broadcasts": {
        "task": "apps.events.programme.broadcast_schedule.resume_scheduled_broadcasts",
        "schedule": crontab(minute="*"),
    },
    "event-asset-work": {"task": "apps.events.tasks_assets.sweep_asset_work_task", "schedule": crontab(minute="*")},
    "event-asset-deadlines": {"task": "apps.events.tasks_assets.sweep_asset_deadlines_task", "schedule": crontab(minute="*")},
    "event-asset-retention": {"task": "apps.events.tasks_assets.sweep_asset_retention_task", "schedule": crontab(minute="*/5")},
    "event-asset-obligations": {"task": "apps.events.tasks_assets.reconcile_asset_obligations_task", "schedule": crontab(minute="*/5")},
    "event-certificate-batches": {"task": "apps.events.certificates.tasks.resume_batches", "schedule": crontab(minute="*")},
    "event-certificate-renders": {"task": "apps.events.certificates.tasks.resume_certificates", "schedule": crontab(minute="*/5")},
    "event-print-cleanup": {"task": "apps.events.tasks_recovery.sweep_print_cleanup_task", "schedule": crontab(minute="*/5")},
    "event-judging-notices": {"task": "apps.events.tasks_recovery.sweep_judging_notices_task", "schedule": crontab(minute="*")},
    # Stage forms (Events core), travel-support deadlines (event_reimbursements) and the core
    # payout ledger's upload recovery and retention. Each per-subject step gates its host.
    "event-stage-reconcile": {"task": "apps.events.staged_forms.tasks.reconcile_stage_forms_task", "schedule": crontab(minute="*/5")},
    "event-stage-file-recovery": {"task": "apps.events.staged_forms.tasks.recover_stage_files_task", "schedule": crontab(minute="*/5")},
    "event-stage-file-retention": {"task": "apps.events.staged_forms.tasks.sweep_stage_file_retention_task", "schedule": crontab(hour=3, minute=50)},
    "event-reimbursement-deadlines": {"task": "apps.event_reimbursements.tasks.sweep_deadlines_task", "schedule": crontab(minute="*/5")},
    "finance-event-payout-recovery": {"task": "apps.payments.event_payouts.tasks.recover_finance_work_task", "schedule": crontab(minute="*/5")},
    "finance-event-payout-retention": {"task": "apps.payments.event_payouts.tasks.sweep_retention_task", "schedule": crontab(hour=3, minute=55)},
    "account-saved-details": {
        "task": "apps.accounts.saved_details.tasks.process_saved_details",
        "schedule": crontab(minute="*/5"),
    },
    # Spent email/phone verification challenges hold an address or a number and nothing
    # deleted them. Off-peak because it is a pure delete nobody is waiting on.
    "purge-auth-challenges": {
        "task": "apps.accounts.tasks.purge_auth_challenges_task",
        "schedule": crontab(hour=3, minute=30),
    },
    # Hosting requests: delete unconfirmed public submissions after 48 h and wipe the
    # applicant's details from dead requests after 90 days. Runs on self-host too.
    "hosting-request-retention": {
        "task": "apps.hosting_requests.tasks.sweep_hosting_requests_task",
        "schedule": crontab(hour=3, minute=45),
    },
    # Maker-profile GitHub counts. Daily and off-peak: the cache interval is 24h, the
    # data is a vanity number, and nothing is waiting on it. A deployment with no
    # GITHUB_API_TOKEN makes no outbound call at all -- the task returns immediately.
    "refresh-github-contributions": {
        "task": "apps.makerspaces.tasks.refresh_github_contributions_task",
        "schedule": crontab(hour=4, minute=15),
    },
    "cleanup-public-page-assets": {
        "task": "apps.makerspaces.tasks.cleanup_public_page_assets_task",
        "schedule": crontab(minute=10),
    },
    "membership-renewals": {
        "task": "apps.makerspaces.tasks_membership.run_membership_renewals_task",
        "schedule": crontab(minute=30),
    },
    "purge-expired-kiosk-operator-leases": {
        "task": "apps.makerspaces.tasks_station.purge_expired_operator_leases_task",
        "schedule": crontab(hour=3, minute=25),
    },
    "purge-expired-data-exports": {
        "task": "apps.data_export.tasks.purge_expired_exports_task",
        "schedule": crontab(hour=3, minute=45),
    },
    "finalize-report-rollups": {
        "task": "apps.operations.tasks.finalize_report_rollups_task",
        "schedule": crontab(hour=1, minute=0),
    },
    "report-schedules": {
        "task": "apps.operations.tasks_report_schedules.run_report_schedules_task",
        "schedule": crontab(minute="*/15"),
    },
    "scheduled-deployment-backup": {
        "task": "apps.backup.tasks.scheduled_deployment_backup_task",
        "schedule": crontab(hour=2, minute=0),
    },
    # Nightly one-space archives (#111 Q4): two due spaces per tick, oldest first, off
    # the same automatic-backups switch; 01:00-07:50 covers 84 spaces a night.
    "scheduled-space-backups": {
        "task": "apps.backup.tasks.scheduled_space_backups_task",
        "schedule": crontab(hour="1-7", minute="*/10"),
    },
    # Picks up a per-space restore step whose dispatch was lost, one per tick.
    "resume-space-restores": {
        "task": "apps.backup.tasks_space_restore.resume_space_restores_task",
        "schedule": crontab(minute="*/5"),
    },
    "reconcile-backup-artifacts": {
        "task": "apps.backup.tasks.reconcile_backup_artifacts_task",
        "schedule": crontab(minute="*/5"),
    },
    # Offsite destinations: enqueue, push+verify and prune. Never under the backup
    # operation lock, and an outage only backs the journal row off.
    "push-offsite-backups": {
        # The registered name: the task is defined in tasks_offsite (tasks.py only re-exports it).
        "task": "apps.backup.tasks_offsite.push_offsite_backups_task",
        "schedule": crontab(minute="*/5"),
    },
    "purge-expired-backup-archives": {
        "task": "apps.backup.tasks.purge_expired_backup_archives_task",
        "schedule": crontab(hour=3, minute=55),
    },
    "cleanup-expired-restore-rollbacks": {
        "task": "apps.backup.tasks.cleanup_expired_restore_rollbacks_task",
        "schedule": crontab(hour=4, minute=5),
    },
    "cleanup-expired-tenant-import-jobs": {
        "task": "apps.tenant_migration.tasks.cleanup_expired_import_jobs_task",
        "schedule": crontab(minute=20),
    },
    "cleanup-abandoned-tenant-import-objects": {
        "task": "apps.tenant_migration.tasks.cleanup_abandoned_import_objects_task",
        "schedule": crontab(minute=35),
    },
    "cleanup-refused-tenant-dump-artifacts": {
        "task": "apps.tenant_migration.tasks.cleanup_refused_tenant_dump_artifacts_task",
        "schedule": crontab(minute=40),
    },
    "resume-expired-tenant-import-finalizations": {
        "task": "apps.tenant_migration.tasks.resume_expired_finalizing_import_jobs_task",
        "schedule": crontab(minute="*/5"),
    },
}
