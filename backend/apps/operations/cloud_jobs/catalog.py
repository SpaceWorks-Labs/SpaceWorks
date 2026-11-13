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
    ("scheduled-space-backups", "apps.backup.tasks.scheduled_space_backups_task", 10),
    ("resume-space-restores", "apps.backup.tasks_space_restore.resume_space_restores_task", 5),
    ("reconcile-backup-artifacts", "apps.backup.tasks.reconcile_backup_artifacts_task", 5),
    ("push-offsite-backups", "apps.backup.tasks_offsite.push_offsite_backups_task", 5),
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
    ("pii-access-expiry", "apps.accounts.tasks.expire_pii_access_windows_task", 5),
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
    # Release 2 L2: bounded per-space sweeps (digest, GitHub flag, reconcile, re-ping, room health).
    ("event-approval-digest", "apps.events.approval_digest.send_approval_digests_task", 30),
    ("event-submission-integrity", "apps.events.submissions.integrity_jobs.sweep_integrity_checks_task", 15),
    ("event-storage-reconcile", "apps.events.submissions.storage_reconcile.reconcile_event_storage_task", 1440),
    ("notification-escalation", "apps.notifications.escalation.escalate_unseen_task", 5),
    ("notification-destination-health", "apps.integrations.destination_health.disable_dead_destinations_task", 60),
    # Lane L5: read-only provider poll of open attempts and pending refunds.
    ("payment-gateway-poll", "apps.payments.tasks.run_gateway_poll_task", 5),
    # Release 2 L11: one due restore drill per tick; a bounded batch of requested re-encryption.
    ("restore-drill", "apps.backup.tasks.run_restore_drill_task", 60),
    ("reencrypt-backup-archives", "apps.backup.tasks.reencrypt_archives_task", 10),
    # Lane L12: loan pickup expiry + waitlist lapses; machine job quotes, pickups, prepay.
    ("loan-pickups", "apps.hardware_requests.tasks_loans.sweep_loan_pickups_task", 15),
    ("machine-job-flow", "apps.machines.tasks_jobs.sweep_job_flow_task", 15),
    # Lane L23: machine sessions that reached their max length, check-out or closing time.
    ("machine-sessions", "apps.machines.tasks_sessions.sweep_machine_sessions_task", 5),
    # Release 2 S-C: IP auto-block rows 7 d after they end; axes rows after 30 d.
    # 0.12.0 channel analytics: cached call counts by channel and area into ChannelUsageDay.
    ("flush-channel-usage", "apps.accounts.tasks_channel_usage.flush_channel_usage_task", 1),
    ("purge-login-security", "apps.accounts.tasks_login_security.purge_login_security_task", 1440),
    # Lane L3: card jobs (one chunk per job per tick), 7-day result purge, wallet refresh, photo reminders.
    ("card-jobs", "apps.card_designs.tasks.resume_card_jobs", 1),
    ("card-job-results", "apps.card_designs.tasks.purge_expired_card_job_results", 60),
    ("card-wallet-refresh", "apps.card_designs.tasks.refresh_wallet_passes", 30),
    ("card-photo-reminders", "apps.card_designs.tasks.remind_photo_requests", 60),
    ("event-id-cards", "apps.events.tasks_id_cards.reconcile_event_id_cards_task", 15),
    # Lane L8: one bounded chunk of each running per-space key rotation, re-key or re-index.
    ("advance-key-jobs", "apps.encryption.rekey_tasks.advance_key_jobs_task", 1),
    # Lane L6: expired checkout holds, missed order settlements and one payment reminder.
    ("event-order-checkouts", "apps.events.reminders_payments.sweep_order_checkouts_task", 1),
    # Lane L18: due pledge periods raise their gift and charge; sponsor perks due tell staff once.
    ("donation-pledges", "apps.payments.donations.tasks.raise_pledges_task", 60),
    ("sponsor-perk-reminders", "apps.payments.donations.tasks.remind_perks_task", 1440),
    # Lane L22: lapsed shop holds, missed shop settlements and uncollected-order reminders.
    ("shop-sweep", "apps.shop.tasks.sweep_shop_task", 1),
    # r2-superadmin-controls (#185, #187A): schedules + reminders, announcement mail, managed hosting.
    ("space-control-schedules", "apps.space_controls.tasks.run_space_schedules_task", 60),
    ("platform-announcement-emails", "apps.space_controls.tasks.send_announcement_emails_task", 5),
    ("managed-hosting-sweep", "apps.managed_hosting.tasks.sweep_managed_hosting_task", 60),
    ("limit-threshold-sweep", "apps.managed_hosting.tasks.sweep_limit_thresholds_task", 30),  # decision 328a
    # Device Adapter API (decisions 312, 321): the managed DatabaseScheduler dispatches only catalogue rows.
    ("adapter-safety-sweep", "apps.devices.tasks.adapter_safety_sweep_task", 1),
    ("adapter-webhook-sweep", "apps.devices.tasks.adapter_webhook_sweep_task", 1),
    ("adapter-media-sweep", "apps.devices.tasks.adapter_media_sweep_task", 10),
    ("purge-adapter-recordings", "apps.devices.tasks.purge_adapter_recordings_task", 1440),
)
_RETAINED = frozenset({
    "evidence-object-expiry", "evidence-abandoned-upload-cleanup",
    "purge-expired-data-exports", "cleanup-kiosk-replay-commands",
    "purge-expired-kiosk-operator-leases", "purge-auth-challenges",
    "reconcile-backup-artifacts", "push-offsite-backups",
    "purge-expired-backup-archives", "cleanup-expired-restore-rollbacks",
    "cleanup-expired-tenant-import-jobs", "cleanup-abandoned-tenant-import-objects",
    "cleanup-refused-tenant-dump-artifacts", "resume-expired-tenant-import-finalizations",
    # Events byte retention and custody must outlive a tombstoned Events app.
    "event-asset-work", "event-asset-retention", "event-asset-obligations", "event-print-cleanup",
    "event-stage-file-retention", "finance-event-payout-retention",
})
_HEAVY = frozenset({
    # Events scans, renders and validation (#89b): one heavy chunk starts per tick.
    "event-asset-work", "event-certificate-batches", "event-certificate-renders",
    "event-stage-file-recovery", "finance-event-payout-recovery",
    "subject-access-exports", "report-schedules", "scheduled-deployment-backup", "scheduled-space-backups",
    "resume-space-restores",
    "reconcile-backup-artifacts", "push-offsite-backups",
    "resume-expired-tenant-import-finalizations", "finalize-report-rollups",
    "restore-drill", "reencrypt-backup-archives", "advance-key-jobs",
    "card-jobs", "card-wallet-refresh",
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


# Legacy beat keys (settings CELERY_BEAT_SCHEDULE) that already schedule the same work
# as a programme wrapper. Selecting the programme must retire them in the same review.
PROGRAMME_LEGACY_KEYS = {
    "event-certificate-resume": "event-certificate-renders", "stage-form-reconcile": "event-stage-reconcile",
    "stage-file-retention": "event-stage-file-retention", "reimbursement-deadlines": "event-reimbursement-deadlines",
    "finance-work": "finance-event-payout-recovery", "finance-retention": "finance-event-payout-retention",
}


def assert_no_programme_overlap(programmes, beat_schedule, mode):
    """A wrapper and a legacy entry for the same work must never both be scheduled."""
    if not programmes:
        return
    from django.core.exceptions import ImproperlyConfigured
    if mode != "managed":
        raise ImproperlyConfigured("Cloud programmes are managed-only; host schedules stay as shipped.")
    rows = [(key, path) for group, key, path, *_ in PROGRAMME_ENTRIES if group in programmes]
    keys = {key for key, _ in rows} | {PROGRAMME_LEGACY_KEYS[key] for key, _ in rows if key in PROGRAMME_LEGACY_KEYS}
    paths = {path for _, path in rows}
    clash = sorted(name for name, entry in beat_schedule.items() if name in keys or entry.get("task") in paths)
    if clash:
        raise ImproperlyConfigured("Retire the legacy schedule entries a cloud programme replaces: " + ", ".join(clash))


def legacy_schedule():
    return tuple((task.key, task.path, task.minutes) for task in periodic_catalog())


def beat_entries():
    """I replaces the shared declaration; daily clock slots stay in settings."""
    return {task.key: {"task": task.path, "schedule": task.minutes * 60.0}
            for task in periodic_catalog()}


def provider_inventory():
    return [asdict(task) for task in periodic_catalog()]

