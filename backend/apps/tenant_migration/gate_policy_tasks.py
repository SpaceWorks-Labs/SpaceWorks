"""Explicit source-gate tasks participation declarations."""

from .gate_policy_replay import REPLAY_TASK_PARTICIPANTS, REPLAY_FANOUT_PARTICIPANTS


TASK_EXEMPTIONS = {
    "apps.integrations.tasks_messaging_settings.wipe_messaging_credentials_task": (
        "Deployment-local callback credential retention: wipes expired verification material "
        "on operational credential versions, never tenant settings or portable domain rows. "
        "Must continue after source migration and channel uninstall."
    ),
    "apps.accounts.tasks.revoke_apple_tokens_task": "Platform-global Apple credential revocation; no tenant writes.",
    "apps.accounts.saved_details.tasks.process_saved_details": (
        "Global account-owned vault work takes global/account fences and cannot mutate tenant event rows."
    ),
    "apps.operations.tasks_platform.run_platform_problem_checks_task": (
        "Read-only platform monitoring; writes only a disposable deployment cache marker."
    ),
    "apps.accounts.tasks.purge_auth_challenges_task": "Platform-global auth retention.",
    "apps.hosting_requests.tasks.sweep_hosting_requests_task": (
        "Platform-global hosting-request retention; deletes/redacts OMITTED platform rows, "
        "no tenant writes."
    ),
    "apps.accounts.tasks.drain_password_reset_envelopes_task": "Platform-global account recovery.",
    "apps.audit.tasks.run_audit_attestation_task": (
        "Deployment-local audit attestation: batches and leaves are deployment "
        "state (OMITTED_MODELS), not tenant domain data, and sealing appends only "
        "to that state."
    ),
    "apps.backup.tasks.run_backup_archive_task": "Deployment/tenant backup control plane.",
    "apps.backup.tasks.scheduled_deployment_backup_task": "Deployment backup control plane.",
    "apps.backup.tasks.purge_expired_backup_archives_task": "Platform backup retention.",
    "apps.backup.tasks.cleanup_expired_restore_rollbacks_task": "Deployment recovery cleanup.",
    "apps.backup.tasks.deliver_archive_custody_alarms_task": (
        "Archive-custody alarm delivery. Writes only its own outbox rows and the "
        "derived custody-state delivery marker -- both deployment control-plane "
        "state, never tenant domain data -- and sends mail. It reads a makerspace "
        "to resolve recipients but mutates no tenant row, so it cannot disturb a "
        "frozen source."
    ),
    "apps.backup.tasks.deliver_tenant_exit_custody_alarms_task": (
        "Lane D custody-alarm delivery writes only deployment-local derived state "
        "and its recoverable outbox before sending mail."
    ),
    "apps.backup.tasks_offsite.push_offsite_backups_task": (
        "Deployment offsite copy control plane: pushes, prunes and re-verifies sealed archives."
    ),
    "apps.backup.tasks_offsite.rehydrate_backup_archive_task": (
        "Deployment recovery: rehydrates a sealed archive from an offsite destination."
    ),
    "apps.backup.tasks.reconcile_backup_artifacts_task": (
        "Deployment-local backup staging, verification, and artifact ledger recovery."
    ),
    "apps.tenant_migration.tasks.cleanup_expired_import_jobs_task": "Target-side import retention and recovery.",
    "apps.tenant_migration.tasks.cleanup_abandoned_import_objects_task": "Target-side import object rollback does not mutate the frozen source.",
    "apps.tenant_migration.tasks.cleanup_refused_tenant_dump_artifacts_task": (
        "Lane D unpublished-byte cleanup mutates only source-deployment coordination state."
    ),
    "apps.tenant_migration.tasks.resume_expired_finalizing_import_jobs_task": "Target-side import finalization recovery does not mutate the frozen source.",
    "apps.tenant_migration.tasks.run_import_job_task": "Target-side tenant materialization does not mutate the frozen source.",
    "apps.tenant_migration.tasks.stage_import_job_task": "Target-side import staging does not mutate the frozen source.",
    "apps.operations.cloud_jobs.diagnostics.installer_roundtrip": (
        "Installer scheduler diagnostics: writes one short-lived cache nonce, never tenant data."
    ),
    "apps.operations.cloud_jobs.maintenance.refresh_storage": (
        "Deployment storage-capability qualification: probes configured buckets only."
    ),
    "apps.operations.cloud_jobs.maintenance.sample_storage": (
        "Deployment storage-usage sampling: writes only deployment accounting rows."
    ),
    "apps.operations.cloud_jobs.maintenance.cleanup_staging": (
        "Managed private-staging cleanup is deployment coordination state, not tenant data."
    ),
}


TASK_TENANT_RESOLVERS = {
    "apps.events.certificates.tasks.process_batch": ("events.CertificateIssueBatch", 0, "event__makerspace_id"),
    "apps.events.certificates.tasks.render_one": ("events.EventAttendanceCertificate", 0, "event__makerspace_id"),
    "apps.events.broadcast_channels.event_broadcast_channels": (
        "events.EventBroadcast", 0, "makerspace_id"
    ),
    "apps.data_export.subject_tasks.run_subject_export_task": (
        "data_export.DataExportJob", 0, "makerspace_id"
    ),
    "apps.admin_api.tasks.process_bulk_import_job": (
        "admin_api.BulkImportJob", 0, "makerspace_id"
    ),
    "apps.audit.tasks.run_audit_verification": (
        "audit.AuditVerificationRun", 0, "makerspace_id"
    ),
    "apps.data_export.tasks.run_data_export_task": (
        "data_export.DataExportJob", 0, "makerspace_id"
    ),
    "apps.integrations.tasks.deliver_email_task": (
        "integrations.EmailLog", 0, "makerspace_id"
    ),
    "apps.integrations.tasks.deliver_notification_task": (
        "integrations.NotificationDeliveryLog", 0, "makerspace_id"
    ),
}


TASK_INTERNAL_PARTICIPANTS = {
    "apps.integrations.notification_tasks.deliver_envelope": (
        "Cutover fence precedes per-leg tenant boundaries; no external call holds an application transaction."
    ),
    "apps.events.tasks_assets.sweep_asset_work_task": "Each live scan enters B's ordered boundary; byte cleanup enters only the retained boundary.",
    "apps.events.tasks_assets.sweep_asset_deadlines_task": "Each due event enters the canonical B source boundary before workflow locks.",
    "apps.events.tasks_assets.sweep_asset_retention_task": "Expiry uses the narrow retained source lock and recovery/not-restored checks; no publication authority.",
    "apps.events.tasks_assets.reconcile_asset_obligations_task": "Permanent FK-free custody reconciliation deletes only exact reserved locators; survives tenant purge.",
    "apps.events.tasks_recovery.sweep_judging_notices_task": "Judging notice dispatch re-enters the live source boundary for each notice.",
    "apps.events.tasks_recovery.sweep_print_cleanup_task": "Retained print cleanup gates recovery and touches only owned expired/cancelled bytes.",
    "apps.events.certificates.tasks.resume_batches": "Dispatches persisted batch IDs to the existing tenant-resolved worker; it grants no issuance authority.",
    "apps.events.certificates.tasks.resume_certificates": "Dispatches persisted certificate IDs to the existing tenant-resolved renderer; it grants no issuance authority.",
    "apps.events.tasks_contributions.sweep_contributor_maintenance_task": "Each tenant is skip-and-count gated before domain maintenance or provider delivery.",
    "apps.events.programme.broadcast_schedule.resume_scheduled_broadcasts": (
        "recover_for_tenants establishes a source boundary for each due campaign."
    ),
    "apps.events.tasks_programme.sweep_admission_deadlines_task": (
        "Each bounded admission service establishes the event host's source boundary before fences and domain locks."
    ),
    "apps.integrations.notification_tasks.sweep_notification_outbox": (
        "Enqueues tenant-resolved delivery tasks; media cleanup uses per-tenant skip-and-count gates."
    ),
    "apps.payments.tasks.issue_missing_bills_task": "Bill recovery gates each tenant before discovering or issuing documents.",
    "apps.payments.tasks.rebuild_refund_cases_task": "Refund-case rebuild gates each tenant before discovering or opening cases.",
    "apps.integrations.tasks_messaging.deliver_messaging_task": "Worker acquires sender lock first and holds tenant_write during claims and fenced completion.",
    "apps.integrations.tasks_messaging.sweep_messaging_task": "Replays durable signed ingress receipts through notification_ingress.process, which holds the cutover/tenant boundary per receipt; sender protections and retired-verifier retention are deployment-local.",
    "apps.integrations.tasks_messaging.canonical_retention_task": (
        "Canonical leg retention uses per-tenant skip-and-count gates; processed receipts are deployment-local."
    ),
    "apps.inventory.tasks.snapshot_stock_task": "Daily stock observations gate each tenant separately.",
    "apps.notifications.tasks.deliver_member_push": (
        "Resolves the canonical envelope delivery's tenant and holds its source boundary; "
        "an optional inbox never provides sending authority."
    ),
    "apps.notifications.tasks.sweep_member_push": (
        "Recovery enqueues each tenant's rows inside a skip-and-count source boundary."
    ),
    "apps.accounts.tasks.purge_deleted_accounts_task": "Account erasure uses one skip-and-count boundary per tenant.",
    "apps.integrations.broadcasts_worker.broadcast_batch": "Typed adapter resolves one tenant; shared source and PII fences precede campaign/outbox locks.",
    "apps.integrations.broadcasts_worker.resume_broadcasts": "Campaign/outbox recovery uses per-tenant skip-and-count boundaries.",
    "apps.data_export.subject_tasks.sweep_subject_exports_task": (
        "Queued personal exports use separate skip-and-count tenant boundaries."
    ),
    "apps.operations.tasks_admissions.sweep_membership_admissions_task": (
        "Admission expiry and committed-settlement recovery gate each tenant before writes."
    ),
    "apps.operations.tasks_reminders.run_reminder_sweep_task": (
        "Reminder discovery, claims and dispatch use one skip-and-count tenant boundary."
    ),
    **REPLAY_TASK_PARTICIPANTS,
    "apps.devices.tasks.scan_offline_devices_task": "Offline/retention service gates each tenant separately.",
    "apps.tenant_migration.tasks.run_migration_export_job_task": (
        "The source export claims and holds source_archive_write for its full lifecycle."
    ),
    "apps.evidence.tasks.cleanup_abandoned_evidence_uploads_task": (
        "New cleanup uses the skip-and-count tenant boundary; receipt reconciliation is "
        "declared deployment coordination."
    ),
    "apps.data_export.tasks.purge_expired_exports_task": (
        "Each expired export uses the skip-and-count tenant boundary."
    ),
    "apps.hardware_requests.tasks.send_return_reminders_task": (
        "Each reminder lifecycle uses the skip-and-count tenant boundary."
    ),
    "apps.evidence.tasks.sweep_evidence_retention_task": (
        "Each evidence expiry uses the skip-and-count tenant boundary."
    ),
    "apps.events.tasks.extend_event_series_task": (
        "Each series extension locks its own makerspace and uses the skip-and-count "
        "tenant boundary; the queryset is servable-filtered before iteration."
    ),
    "apps.operations.tasks.finalize_report_rollups_task": (
        "Each rollup finalisation uses the skip-and-count tenant boundary; the "
        "makerspace queryset is servable-filtered before iteration."
    ),
    "apps.operations.tasks_report_schedules.run_report_schedules_task": (
        "Each due schedule runs inside its own skip-and-count tenant boundary; the "
        "due queryset is filtered to report-eligible (servable) makerspaces first."
    ),
    "apps.makerspaces.tasks.refresh_github_contributions_task": (
        "Each profile refresh uses the skip-and-count tenant boundary."
    ),
    "apps.makerspaces.tasks_membership.run_membership_renewals_task": (
        "Each term expiry and renewal charge uses the skip-and-count tenant boundary."
    ),
    "apps.apiclients.tasks.flush_api_client_usage_task": (
        "Writes only deployment-local last-seen telemetry on ApiClient rows; it moves no "
        "tenant data and so needs no per-tenant gate."
    ),
    "apps.makerspaces.tasks_station.purge_expired_operator_leases_task": (
        "Each tenant's expired kiosk leases use the skip-and-count tenant boundary."
    ),
    "apps.events.tasks_cloud.process_asset_work_task": (
        "Each submission asset job runs inside its event tenant's skip-and-count boundary."
    ),
    "apps.events.tasks_cloud.resume_certificates_task": (
        "Each certificate batch chunk and render uses its event tenant's skip-and-count boundary."
    ),
    "apps.events.tasks_cloud.sweep_asset_lifecycle_task": (
        "Delegates to the installed Events runtime callback, which owns its per-tenant source fences."
    ),
    "apps.events.tasks_cloud.cleanup_print_jobs_task": (
        "Delegates to the Events certificate print cleanup, which owns its per-tenant source fences."
    ),
    "apps.events.tasks_cloud.cleanup_programme_receipts_task": (
        "Delegates to the installed Events runtime callback, which owns its per-tenant source fences."
    ),
    "apps.events.tasks_cloud.sweep_stage_file_retention_task": (
        "Delegates to the installed Events runtime callback, which owns its per-tenant source fences."
    ),
}


FANOUT_GATE_PARTICIPANTS = {
    "apps.events.judging.lifecycle.sweep_notices": "Each persisted result notice re-enters skip-and-count source boundary before delivery.",
    "apps.events.tasks_contributions.sweep_contributor_maintenance_task": "Contributor lease expiry, escalation and committed-notice recovery.",
    "apps.integrations.notification_media.cleanup_grants": (
        "Expired and consumed disclosure grants are deleted and audited inside each tenant gate."
    ),
    "apps.payments.bill_sweeper.issue_missing_bills": "Core bill recovery uses per-tenant skip-and-count source gates.",
    "apps.payments.refund_case_sweeper.rebuild_missed_refund_cases": "Refund-case rebuild uses per-tenant skip-and-count source gates.",
    "apps.makerspaces.profile_github_tasks.refresh_public_calendars": (
        "Public calendars refresh under the existing per-tenant GitHub source boundary; cache only."
    ),
    "apps.integrations.messaging.stops.append_stop_consents": "Optional consent annotations skip frozen tenants after committing sender-level STOP protection.",
    "apps.integrations.notification_legacy_ingress.inbound": "Per-tenant endpoint effects of a signed inbound skip frozen tenants; sender-level STOP already committed and the receipt stays held for recovery.",
    "apps.inventory.stock_snapshots.snapshot_inventory_stock": "Daily stock observations gate each tenant separately.",
    "apps.notifications.tasks.sweep_member_push": "Member push recovery gates each tenant separately.",
    "apps.accounts.account_purge.purge_account": "Account erasure and durable object cleanup gate each tenant separately.",
    "apps.integrations.broadcasts_worker.recover_for_tenants": "Recover durable campaigns and outboxes only inside each tenant's source gate.",
    "apps.data_export.subject_tasks.sweep_subject_exports_task": "Personal export recovery gates each tenant.",
    "apps.makerspaces.membership_admission_payments.sweep_admissions": (
        "Admission expiry and settlement retries use separate skip-and-count tenant boundaries."
    ),
    "apps.integrations.notification_retention.run_canonical_retention": (
        "Terminal addressed-leg cleanup gates each tenant separately."
    ),
    "apps.notifications.retention.run_notification_retention": (
        "Bounded inbox and terminal delivery cleanup gates each tenant separately."
    ),
    "apps.operations.reminder_sweeper.run_reminder_sweep": (
        "Shared source-local reminders; each tenant is gated before discovery or dispatch."
    ),
    **REPLAY_FANOUT_PARTICIPANTS,
    "apps.devices.services_offline.scan_offline_devices": "Device offline edges and auth-artifact retention.",
    "apps.data_export.tasks.purge_expired_exports_task": "Expired export cleanup.",
    "apps.evidence.abandoned_upload_cleanup.sweep_abandoned_evidence_uploads": (
        "Abandoned evidence-upload cleanup."
    ),
    "apps.evidence.services_retention.sweep_evidence_retention": (
        "Evidence object expiry."
    ),
    "apps.hardware_requests.services_return_reminders._run_legacy_return_reminders": (
        "Overdue loan reminders."
    ),
    "apps.makerspaces.tasks.refresh_github_contributions_task": "GitHub profile refresh.",
    "apps.makerspaces.membership_renewals.run_membership_renewals": (
        "Membership term expiry and renewal charges."
    ),
    "apps.operations.report_schedule_services.run_report_schedules": "Due scheduled report deliveries.",
    "apps.makerspaces.station_lease_cleanup.purge_expired_operator_leases": (
        "Expired kiosk operator lease cleanup."
    ),
    "apps.events.tasks_cloud.process_asset_work_task": "Bounded submission asset work.",
    "apps.events.tasks_cloud.resume_certificates_task": "Bounded certificate batch and render recovery.",
    "apps.admin_api.cloud_work.chunk": "Free-profile bulk-import page (one job per chunk).",
    "apps.integrations.mail_providers.channel_chunks.drain_channels": (
        "Free-profile legacy channel delivery (one row per chunk)."
    ),
    "apps.integrations.mail_providers.chunks._phase": "Free-profile contract envelope delivery (one per chunk).",
    "apps.integrations.mail_providers.outbox.drain": (
        "Free-profile mail drain; platform and custody-alarm mail stay ungated."
    ),
    "apps.operations.cloud_jobs.rollups.chunk": "Free-profile report rollup finalisation.",
}

from .catalog_p2_presence import gate_tasks
gate_tasks(TASK_INTERNAL_PARTICIPANTS, FANOUT_GATE_PARTICIPANTS)
TASK_INTERNAL_PARTICIPANTS["apps.makerspaces.tasks.cleanup_public_page_assets_task"] = (
    "Typed tenant cleanup uses per-tenant fanout and repeats the write fence under owner locks; organization cleanup is global."
)
FANOUT_GATE_PARTICIPANTS["apps.makerspaces.public_page_asset_cleanup.sweep"] = "Typed private-page byte cleanup."
from .source_gate_reimbursements import gate_tasks as gate_reimbursement_tasks
gate_reimbursement_tasks(TASK_INTERNAL_PARTICIPANTS)
from .gate_policy_r2_l2 import gate_tasks as gate_r2_l2_tasks
gate_r2_l2_tasks(TASK_INTERNAL_PARTICIPANTS)
