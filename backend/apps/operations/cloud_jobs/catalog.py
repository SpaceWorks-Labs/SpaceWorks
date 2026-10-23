"""Single periodic inventory; no domain imports while inspecting a deployment."""
from dataclasses import asdict, dataclass
from importlib import import_module

from django.conf import settings


@dataclass(frozen=True)
class PeriodicTask:
    key: str
    path: str
    minutes: int
    app: str = ""
    retained: bool = False
    operation: str = "domain_owned"
    batch: str = "domain_lease"
    writer: str = "cron"
    heavy: bool = False
    critical: bool = False
    free_policy: str = "bounded_adapter_required"

    def resolve(self):
        module, _, attribute = self.path.rpartition(".")
        return getattr(import_module(module), attribute)


# Legacy entries retain their exact names, intervals and first-run warm-up.
LEGACY_ENTRIES = (
    ("missing-payment-bills", "apps.payments.tasks.issue_missing_bills_task", 5),
    ("rebuild-refund-cases", "apps.payments.tasks.rebuild_refund_cases_task", 60),
    ("presence-expiry", "apps.presence.tasks.expire_presence_sessions_task", 1),
    ("notification-contract-outbox", "apps.integrations.notification_tasks.sweep_notification_outbox", 1),
    ("subject-access-exports", "apps.data_export.subject_tasks.sweep_subject_exports_task", 60),
    ("reminder-sweep", "apps.operations.tasks_reminders.run_reminder_sweep_task", 5),
    ("platform-problem-checks", "apps.operations.tasks_platform.run_platform_problem_checks_task", 15),
    ("membership-admissions", "apps.operations.tasks_admissions.sweep_membership_admissions_task", 5),
    ("scan-offline-devices", "apps.devices.tasks.scan_offline_devices_task", 1),
    ("cleanup-kiosk-replay-commands", "apps.hardware_requests.tasks_replay.cleanup_replay_commands_task", 1440),
    ("flush-api-client-usage", "apps.apiclients.tasks.flush_api_client_usage_task", 1),
    ("audit-attestation", "apps.audit.tasks.run_audit_attestation_task", 5),
    ("drain-password-reset-envelopes", "apps.accounts.tasks.drain_password_reset_envelopes_task", 1),
    ("return-reminders", "apps.hardware_requests.tasks.send_return_reminders_task", 60),
    ("evidence-object-expiry", "apps.evidence.tasks.sweep_evidence_retention_task", 360),
    ("evidence-abandoned-upload-cleanup", "apps.evidence.tasks.cleanup_abandoned_evidence_uploads_task", 360),
    ("extend-event-series", "apps.events.tasks.extend_event_series_task", 60),
    ("purge-auth-challenges", "apps.accounts.tasks.purge_auth_challenges_task", 1440),
    ("refresh-github-contributions", "apps.makerspaces.tasks.refresh_github_contributions_task", 1440),
    ("membership-renewals", "apps.makerspaces.tasks_membership.run_membership_renewals_task", 60),
    ("purge-expired-kiosk-operator-leases", "apps.makerspaces.tasks_station.purge_expired_operator_leases_task", 1440),
    ("purge-expired-data-exports", "apps.data_export.tasks.purge_expired_exports_task", 1440),
    ("finalize-report-rollups", "apps.operations.tasks.finalize_report_rollups_task", 1440),
    ("report-schedules", "apps.operations.tasks_report_schedules.run_report_schedules_task", 15),
    ("scheduled-deployment-backup", "apps.backup.tasks.scheduled_deployment_backup_task", 1440),
    ("deliver-archive-custody-alarms", "apps.backup.tasks.deliver_archive_custody_alarms_task", 1440),
    ("deliver-tenant-exit-custody-alarms", "apps.backup.tasks.deliver_tenant_exit_custody_alarms_task", 60),
    ("reconcile-backup-artifacts", "apps.backup.tasks.reconcile_backup_artifacts_task", 5),
    ("push-offsite-backups", "apps.backup.tasks.push_offsite_backups_task", 5),
    ("purge-expired-backup-archives", "apps.backup.tasks.purge_expired_backup_archives_task", 1440),
    ("cleanup-expired-restore-rollbacks", "apps.backup.tasks.cleanup_expired_restore_rollbacks_task", 1440),
    ("cleanup-expired-tenant-import-jobs", "apps.tenant_migration.tasks.cleanup_expired_import_jobs_task", 60),
    ("cleanup-abandoned-tenant-import-objects", "apps.tenant_migration.tasks.cleanup_abandoned_import_objects_task", 60),
    ("cleanup-refused-tenant-dump-artifacts", "apps.tenant_migration.tasks.cleanup_refused_tenant_dump_artifacts_task", 60),
    ("resume-expired-tenant-import-finalizations", "apps.tenant_migration.tasks.resume_expired_finalizing_import_jobs_task", 5),
    # Integrated on staging (Pages, mobile messaging/push/accounts, inventory analytics,
    # hosting): every scheduler runs these exactly as the beat-less command did.
    ("cleanup-public-page-assets", "apps.makerspaces.tasks.cleanup_public_page_assets_task", 60),
    ("messaging-recovery", "apps.integrations.tasks_messaging.sweep_messaging_task", 5),
    ("canonical-messaging-retention", "apps.integrations.tasks_messaging.canonical_retention_task", 60),
    ("messaging-credential-wipe", "apps.integrations.tasks_messaging_settings.wipe_messaging_credentials_task", 1440),
    ("inventory-stock-snapshot", "apps.inventory.tasks.snapshot_stock_task", 1440),
    ("member-push-recovery", "apps.notifications.tasks.sweep_member_push", 5),
    ("purge-deleted-accounts", "apps.accounts.tasks.purge_deleted_accounts_task", 1440),
    ("hosting-request-retention", "apps.hosting_requests.tasks.sweep_hosting_requests_task", 1440),
    # Events programme (lane/events-final): the exact entries its beat-less command ran.
    ("event-admission-deadlines", "apps.events.tasks_programme.sweep_admission_deadlines_task", 5),
    ("event-contributor-maintenance", "apps.events.tasks_contributions.sweep_contributor_maintenance_task", 1),
    ("event-scheduled-broadcasts", "apps.events.programme.broadcast_schedule.resume_scheduled_broadcasts", 1),
    ("event-asset-work", "apps.events.tasks_assets.sweep_asset_work_task", 1),
    ("event-asset-deadlines", "apps.events.tasks_assets.sweep_asset_deadlines_task", 1),
    ("event-asset-retention", "apps.events.tasks_assets.sweep_asset_retention_task", 5),
    ("event-asset-obligations", "apps.events.tasks_assets.reconcile_asset_obligations_task", 5),
    ("event-certificate-batches", "apps.events.certificates.tasks.resume_batches", 1),
    ("event-certificate-renders", "apps.events.certificates.tasks.resume_certificates", 5),
    ("event-print-cleanup", "apps.events.tasks_recovery.sweep_print_cleanup_task", 5),
    ("event-judging-notices", "apps.events.tasks_recovery.sweep_judging_notices_task", 1),
    ("event-stage-reconcile", "apps.events.staged_forms.tasks.reconcile_stage_forms_task", 5),
    ("event-stage-file-recovery", "apps.events.staged_forms.tasks.recover_stage_files_task", 5),
    ("event-stage-file-retention", "apps.events.staged_forms.tasks.sweep_stage_file_retention_task", 1440),
    ("event-reimbursement-deadlines", "apps.event_reimbursements.tasks.sweep_deadlines_task", 5),
    ("finance-event-payout-recovery", "apps.payments.event_payouts.tasks.recover_finance_work_task", 5),
    ("finance-event-payout-retention", "apps.payments.event_payouts.tasks.sweep_retention_task", 1440),
    ("account-saved-details", "apps.accounts.saved_details.tasks.process_saved_details", 5),
)
_RETAINED = frozenset({
    "evidence-object-expiry", "evidence-abandoned-upload-cleanup",
    "purge-expired-data-exports", "cleanup-kiosk-replay-commands",
    "purge-expired-kiosk-operator-leases", "purge-auth-challenges",
    "deliver-archive-custody-alarms", "deliver-tenant-exit-custody-alarms",
    "reconcile-backup-artifacts", "push-offsite-backups",
    "purge-expired-backup-archives", "cleanup-expired-restore-rollbacks",
    "cleanup-expired-tenant-import-jobs", "cleanup-abandoned-tenant-import-objects",
    "cleanup-refused-tenant-dump-artifacts", "resume-expired-tenant-import-finalizations",
    # Events byte retention and custody must outlive a tombstoned Events app.
    "event-asset-work", "event-asset-retention", "event-asset-obligations", "event-print-cleanup",
    "event-stage-file-retention", "finance-event-payout-retention",
})
_HEAVY = frozenset({
    "subject-access-exports", "report-schedules", "scheduled-deployment-backup",
    "reconcile-backup-artifacts", "push-offsite-backups",
    "resume-expired-tenant-import-finalizations", "finalize-report-rollups",
})
_CRITICAL = frozenset({
    "reminder-sweep", "notification-contract-outbox", "drain-password-reset-envelopes",
    "presence-expiry", "evidence-object-expiry", "evidence-abandoned-upload-cleanup",
})
# Imported only after the incoming programme has been reviewed and enabled by I.
PROGRAMME_ENTRIES = (
    # "pages" is integrated: its cleanup task is a legacy entry above.
    ("events", "event-admission-deadlines", "apps.events.tasks_programme.sweep_admission_deadlines_task", 5, False),
    ("events", "event-contributor-maintenance", "apps.events.tasks_contributions.sweep_contributor_maintenance_task", 1, False),
    ("events", "account-saved-details", "apps.accounts.saved_details.tasks.process_saved_details", 5, True),
    ("events", "event-asset-work", "apps.events.tasks_cloud.process_asset_work_task", 1, True),
    ("events", "event-asset-lifecycle", "apps.events.tasks_cloud.sweep_asset_lifecycle_task", 5, True),
    ("events", "event-certificate-resume", "apps.events.tasks_cloud.resume_certificates_task", 5, False),
    ("events", "event-print-cleanup", "apps.events.tasks_cloud.cleanup_print_jobs_task", 60, True),
    ("events", "event-scheduled-broadcasts", "apps.events.programme.broadcast_schedule.resume_scheduled_broadcasts", 1, False),
    ("events", "event-programme-receipts", "apps.events.tasks_cloud.cleanup_programme_receipts_task", 1440, True),
    ("reimbursement", "stage-form-reconcile", "apps.events.staged_forms.tasks.reconcile_stage_forms_task", 5, False),
    ("reimbursement", "reimbursement-deadlines", "apps.event_reimbursements.tasks.sweep_deadlines_task", 5, False),
    ("reimbursement", "finance-work", "apps.payments.event_payouts.tasks.recover_finance_work_task", 5, True),
    ("reimbursement", "finance-retention", "apps.payments.event_payouts.tasks.sweep_retention_task", 1440, True),
    ("reimbursement", "stage-file-retention", "apps.events.tasks_cloud.sweep_stage_file_retention_task", 1440, True),
)

OPERATIONAL_ENTRIES = (
    ("cloud-storage-qualification", "apps.operations.cloud_jobs.maintenance.refresh_storage", 5),
    ("cloud-storage-usage", "apps.operations.cloud_jobs.maintenance.sample_storage", 15),
    ("cloud-private-staging-cleanup", "apps.operations.cloud_jobs.maintenance.cleanup_staging", 60),
)
_ADMISSION_PREREQUISITES = frozenset({"cloud-storage-qualification", "cloud-storage-usage"})


def all_declarations():
    tasks = [PeriodicTask(
        key, path, minutes, app=path.split(".")[1], retained=key in _RETAINED,
        heavy=key in _HEAVY, critical=key in _CRITICAL,
        free_policy="disabled_in_free_profile" if key == "scheduled-deployment-backup"
        else "bounded_adapter_required",
    ) for key, path, minutes in LEGACY_ENTRIES]
    # The events programme is merged, so its own tasks are legacy entries. A programme
    # wrapper never duplicates one by key or by task path.
    legacy_keys = {key for key, _path, _minutes in LEGACY_ENTRIES}
    legacy_paths = {path for _key, path, _minutes in LEGACY_ENTRIES}
    tasks.extend(PeriodicTask(
        key, path, minutes, app=path.split(".")[1],
        retained=retained, heavy=key in {"event-asset-work", "event-certificate-resume", "finance-work"},
        operation=key.replace("-", "_"),
    ) for group, key, path, minutes, retained in PROGRAMME_ENTRIES
        if key not in legacy_keys and path not in legacy_paths)
    # Free uploads are refused until storage is qualified and every binding has a fresh
    # usage sample, so a new deployment must not wait one full interval before the
    # first run of either: seed them due immediately, like the critical sweeps.
    tasks.extend(PeriodicTask(key, path, minutes, app="operations", retained=True,
                              critical=key in _ADMISSION_PREREQUISITES)
                 for key, path, minutes in OPERATIONAL_ENTRIES)
    from .work import WORK
    tasks.extend(PeriodicTask("persisted-" + work.key, work.task, 1, app=work.app,
                              retained=work.app == "tenant_migration", heavy=True)
                 for work in WORK)
    return tuple(tasks)


def periodic_catalog(*, programmes=None, tombstones=None):
    selected = frozenset(getattr(settings, "CLOUD_PROGRAMMES", ()) if programmes is None else programmes)
    if selected - {"pages", "events", "reimbursement"}:
        raise ValueError("Unknown cloud programme")
    tombstones = frozenset(settings.TOMBSTONED_APPS if tombstones is None else tombstones)
    extra = {key for group, key, *_ in PROGRAMME_ENTRIES if group in selected}
    legacy = {row[0] for row in LEGACY_ENTRIES}
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed":
        extra.update(row[0] for row in OPERATIONAL_ENTRIES)
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        from .work import WORK
        extra.update("persisted-" + work.key for work in WORK)
    return tuple(task for task in all_declarations()
                 if task.key in legacy | extra and (task.retained or task.app not in tombstones))


def legacy_schedule():
    return tuple((task.key, task.path, task.minutes) for task in periodic_catalog())


def beat_entries():
    """I replaces the shared declaration; daily clock slots stay in settings."""
    return {task.key: {"task": task.path, "schedule": task.minutes * 60.0}
            for task in periodic_catalog()}


def provider_inventory():
    return [asdict(task) for task in periodic_catalog()]

