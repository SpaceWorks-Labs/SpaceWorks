"""Every scheduled task, mapped to the switch that owns it (#183B, #186).

A module or capability that is off for a space runs no scheduled work there; its rows are
kept and the work resumes when it comes back on. Each task below is either:

* ``gated(source)`` -- skips every space where ``source`` is off, read through
  ``makerspaces.scheduled_scope`` / ``module_enabled`` / ``feature_enabled`` (never a raw
  JSON ``__contains`` alone). ``source`` is a module, a capability, ``a|b`` (either) or a
  tuple (all);
* ``per_row(note)`` -- one task serving several switches; each row or source checks its own
  (the reminder sweep's ``ReminderSource.module/feature``, a card job's scope);
* ``platform(note)`` -- no single space switch owns it: deployment operations, security,
  recovery, the money ledger (permanently core), legal retention, or byte retention that
  must outlive a module. A core module (always on) is listed here too.

``tests/modules/test_scheduled_task_sources.py`` fails when a beat entry, cloud catalogue
row or persisted worker is not mapped here, or names an unknown key.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSource:
    kind: str  # "gated" | "per_row" | "platform"
    source: object = None
    note: str = ""


def gated(source, note=""):
    return TaskSource("gated", source, note)


def per_row(note):
    return TaskSource("per_row", None, note)


def platform(note):
    return TaskSource("platform", None, note)


_RETENTION = "byte/row retention that must outlive the module (data-lifecycle obligation)"
_SECURITY = "account security and authentication housekeeping"
_RECOVERY = "deployment backup, restore and recovery"
_MIGRATION = "tenant migration / self-host move machinery"
_LEDGER = "the payment ledger is permanently core (CLAUDE.md Hard Rules)"
_DELIVERY = "notification delivery infrastructure; every envelope re-checks its source at send (#183B gap 14)"

A = "apps."
TASK_SOURCES = {
    # Accounts, security, platform operations.
    A + "accounts.saved_details.tasks.process_saved_details": platform("per-account saved details, not per-space"),
    A + "accounts.tasks.drain_password_reset_envelopes_task": platform(_SECURITY),
    A + "accounts.tasks.expire_pii_access_windows_task": platform(_SECURITY),
    A + "accounts.tasks.purge_auth_challenges_task": platform(_SECURITY),
    A + "accounts.tasks.purge_deleted_accounts_task": platform("account deletion is a legal obligation"),
    A + "accounts.tasks_login_security.purge_login_security_task": platform(_SECURITY),
    A + "apiclients.tasks.flush_api_client_usage_task": platform("API client metering"),
    A + "audit.tasks.run_audit_attestation_task": platform("append-only audit integrity"),
    A + "audit.tasks.run_audit_verification": platform("append-only audit integrity"),
    A + "encryption.rekey_tasks.advance_key_jobs_task": platform("key rotation"),
    A + "hosting_requests.tasks.sweep_hosting_requests_task": platform("platform onboarding requests"),
    A + "operations.tasks_platform.run_platform_problem_checks_task": platform("deployment health"),
    A + "operations.cloud_jobs.maintenance.cleanup_staging": platform("managed storage maintenance"),
    A + "operations.cloud_jobs.maintenance.refresh_storage": platform("managed storage maintenance"),
    A + "operations.cloud_jobs.maintenance.sample_storage": platform("managed storage maintenance"),
    # Backups, recovery, migration.
    **{A + "backup." + name: platform(_RECOVERY) for name in (
        "tasks.cleanup_expired_restore_rollbacks_task", "tasks.purge_expired_backup_archives_task",
        "tasks.push_offsite_backups_task", "tasks.reconcile_backup_artifacts_task", "tasks.reencrypt_archives_task",
        "tasks.run_restore_drill_task", "tasks.scheduled_deployment_backup_task", "tasks.scheduled_space_backups_task",
        "tasks_space_restore.resume_space_restores_task")},
    **{A + "tenant_migration.tasks." + name: platform(_MIGRATION) for name in (
        "cleanup_abandoned_import_objects_task", "cleanup_expired_import_jobs_task",
        "cleanup_refused_tenant_dump_artifacts_task", "resume_expired_finalizing_import_jobs_task",
        "run_import_job_task", "run_migration_export_job_task", "stage_import_job_task")},
    A + "data_export.subject_tasks.sweep_subject_exports_task": platform("subject-access exports are a legal right"),
    A + "data_export.tasks.purge_expired_exports_task": platform(_RETENTION),
    A + "data_export.tasks.run_data_export_task": platform("staff data export is core"),
    # Evidence and the core loan spine.
    A + "evidence.tasks.cleanup_abandoned_evidence_uploads_task": platform(_RETENTION),
    A + "evidence.tasks.sweep_evidence_retention_task": platform(_RETENTION),
    A + "hardware_requests.tasks_replay.cleanup_replay_commands_task": platform(_RETENTION),
    A + "hardware_requests.tasks.send_return_reminders_task": platform(
        "core loan spine (`request_workflow`): items already out must still come back"),
    A + "hardware_requests.tasks_loans.sweep_loan_pickups_task": gated(
        "loans.pickup_windows", "and its waitlist lapses: loans.waitlist"),
    A + "inventory.tasks.snapshot_stock_task": platform("core inventory"),
    A + "admin_api.tasks.process_bulk_import_job": gated("bulk_import"),
    # Members, cards, profiles.
    A + "makerspaces.tasks.cleanup_public_page_assets_task": platform(_RETENTION),
    A + "makerspaces.tasks.refresh_github_contributions_task": gated("membership"),
    A + "makerspaces.tasks_membership.run_membership_renewals_task": gated("membership"),
    A + "makerspaces.tasks_station.purge_expired_operator_leases_task": platform(_RETENTION),
    A + "operations.tasks_admissions.sweep_membership_admissions_task": gated("membership"),
    A + "card_designs.tasks.resume_card_jobs": per_row("job_runner cancels a job whose card scope is off"),
    A + "card_designs.tasks.purge_expired_card_job_results": platform(_RETENTION),
    A + "card_designs.tasks.refresh_wallet_passes": per_row("card kind + its wallet capability (switches.live_holder_q)"),
    A + "card_designs.tasks.remind_photo_requests": per_row("card kind's switch (switches.live_holder_q)"),
    A + "events.tasks_id_cards.reconcile_event_id_cards_task": gated("events.id_cards"),
    # Machines and devices.
    A + "machines.tasks_jobs.sweep_job_flow_task": gated("machines.job_requests"),
    A + "machines.tasks_sessions.sweep_machine_sessions_task": gated("machines.sessions"),
    A + "devices.tasks.scan_offline_devices_task": gated("devices"),
    A + "presence.tasks.expire_presence_sessions_task": gated("presence"),
    # Events.
    A + "events.approval_digest.send_approval_digests_task": gated("events.approval_digest"),
    A + "events.certificates.tasks.resume_batches": gated("events"),
    A + "events.certificates.tasks.resume_certificates": gated("events"),
    A + "events.programme.broadcast_schedule.resume_scheduled_broadcasts": gated("events.broadcasts"),
    A + "events.reminders_payments.sweep_order_checkouts_task": gated(
        "events.orders", "a missed settlement of an already-paid order is not gated (money in flight)"),
    A + "events.staged_forms.tasks.reconcile_stage_forms_task": gated("events"),
    A + "events.staged_forms.tasks.recover_stage_files_task": gated("events"),
    A + "events.staged_forms.tasks.sweep_stage_file_retention_task": platform(_RETENTION),
    A + "events.submissions.integrity_jobs.sweep_integrity_checks_task": gated("events.submission_integrity"),
    A + "events.submissions.storage_reconcile.reconcile_event_storage_task": gated("events"),
    A + "events.tasks.extend_event_series_task": gated("events"),
    A + "events.tasks_assets.reconcile_asset_obligations_task": platform(_RETENTION),
    A + "events.tasks_assets.sweep_asset_deadlines_task": gated("events.hackathons", "stage reminders: events"),
    A + "events.tasks_assets.sweep_asset_retention_task": platform(_RETENTION),
    A + "events.tasks_assets.sweep_asset_work_task": platform(_RETENTION),
    A + "events.tasks_contributions.sweep_contributor_maintenance_task": gated("events"),
    A + "events.tasks_programme.sweep_admission_deadlines_task": gated("events.hackathons"),
    A + "events.tasks_recovery.sweep_judging_notices_task": gated("events"),
    A + "events.tasks_recovery.sweep_print_cleanup_task": platform(_RETENTION),
    # Managed-only programme wrappers (CLOUD_PROGRAMMES) of the events entries above.
    A + "events.tasks_cloud.cleanup_print_jobs_task": platform(_RETENTION),
    A + "events.tasks_cloud.cleanup_programme_receipts_task": platform(_RETENTION),
    A + "events.tasks_cloud.process_asset_work_task": platform(_RETENTION),
    A + "events.tasks_cloud.resume_certificates_task": gated("events"),
    A + "events.tasks_cloud.sweep_asset_lifecycle_task": platform(_RETENTION),
    A + "events.tasks_cloud.sweep_stage_file_retention_task": platform(_RETENTION),
    A + "event_reimbursements.tasks.sweep_deadlines_task": gated(("events", "event_reimbursements")),
    A + "payments.event_payouts.tasks.recover_finance_work_task": gated(
        ("events", "event_reimbursements"), "its expired-byte cleanup is retention, not gated"),
    A + "payments.event_payouts.tasks.sweep_retention_task": platform(_RETENTION),
    # Money.
    A + "payments.tasks.issue_missing_bills_task": platform(_LEDGER),
    A + "payments.tasks.rebuild_refund_cases_task": platform(_LEDGER),
    A + "payments.tasks.run_gateway_poll_task": platform("money in flight: a provider outcome is recorded once begun"),
    A + "payments.donations.tasks.raise_pledges_task": gated("finance.recurring_donations"),
    A + "payments.donations.tasks.remind_perks_task": gated("finance.sponsors"),
    A + "shop.tasks.sweep_shop_task": gated("shop"),
    # Notifications and messaging.
    A + "integrations.notification_tasks.sweep_notification_outbox": platform(_DELIVERY),
    A + "integrations.tasks_messaging.sweep_messaging_task": platform(_DELIVERY),
    A + "integrations.tasks_messaging.canonical_retention_task": platform(_RETENTION),
    A + "integrations.tasks_messaging_settings.wipe_messaging_credentials_task": platform(_SECURITY),
    A + "integrations.destination_health.disable_dead_destinations_task": per_row("each room's channel module"),
    A + "notifications.tasks.sweep_member_push": platform(_DELIVERY),
    A + "notifications.escalation.escalate_unseen_task": gated("notifications.escalation"),
    # Reports and reminders.
    A + "operations.tasks.finalize_report_rollups_task": gated("reports"),
    A + "operations.tasks_report_schedules.run_report_schedules_task": per_row(
        "reports, plus each report's source modules and capability (report_schedule_services._skip_reason)"),
    A + "operations.tasks_reminders.run_reminder_sweep_task": per_row(
        "each ReminderSource's module and capability (reminder_sweeper._source_enabled); "
        "broadcast recovery re-checks the event's source at send"),
}
