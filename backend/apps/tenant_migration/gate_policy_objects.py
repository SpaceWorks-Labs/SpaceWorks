"""Explicit source-gate objects participation declarations."""

LIFECYCLE_EXEMPTIONS = {
    "apps.encryption.services.rotate_dek": "DEK rotation is expressly excluded from source quiescence.",
    "apps.encryption.services.disable_dek": "DEK lifecycle is expressly excluded from source quiescence.",
    "apps.encryption.services.rewrap_dek": "DEK rotation is expressly excluded from source quiescence.",
    "apps.makerspaces.lifecycle_purge.purge": "Tenant purge is expressly excluded from source quiescence.",
    "apps.makerspaces.lifecycle_archive.archive": "Tenant archive is expressly excluded from source quiescence.",
    "apps.makerspaces.lifecycle_archive._archive_locked": "Cutover's locked tenant archive is expressly excluded.",
}


OBJECT_MUTATION_PARTICIPANTS = {
    "apps.bookings.services_gallery.presign_photo": "Called by the tenant-resolved gallery upload route behind the authenticated source-gate assertion.",
    "apps.bookings.services_gallery.cleanup_unattached": "Failed gallery attachment cleanup runs inside the tenant-resolved photo route's source-gate boundary.",
    "apps.bookings.services_gallery.delete_photo": "Photo removal and post-commit storage release run through the tenant-resolved gallery route.",
    "apps.makerspaces.website_assets.delete_object": "Private website rollback/replacement cleanup belongs to the tenant-resolved durable website transaction or post-commit cleanup.",
    "apps.makerspaces.website_assets.copy_object": "Called only by an authorized domain clone/COW adapter inside clone_transaction and its tenant source gate.",
    "apps.data_export.subject_services.run_subject_export": (
        "The subject task or recovery sweep holds subject_boundary through archive upload and finalization."
    ),
    "apps.data_export.services._fail_job": "Called within the tenant export or scoped personal-export lifecycle boundary.",
    "apps.data_export.services._finalize_job": "Called within the tenant export or scoped personal-export lifecycle boundary.",
    "apps.data_export.services.run_export_job": (
        "The export task resolves and holds the tenant gate for this lifecycle."
    ),
    "apps.evidence.finalization.finalize_upload": "Reached only through the already-declared handover, return and direct-loan entry points.",
    "apps.evidence.abandoned_upload_cleanup._sweep_makerspace": (
        "The fan-out service owns one tenant source-gate boundary at a time."
    ),
    "apps.evidence.abandoned_upload_reconciliation._reconcile_receipt": (
        "Deployment coordination: deletes only receipt-named keys and updates receipt "
        "scheduling, so it must keep running after MIGRATED_OUT and tenant purge."
    ),
    "apps.evidence.services_retention._sweep_makerspace": (
        "The fan-out service owns one tenant source-gate boundary at a time."
    ),
    "apps.events.services_images.remove_image": "Called by the tenant-resolved event image route.",
    "apps.makerspaces.member_card_storage.presign_photo": "Called only by the tenant-resolved member-card photo route.",
    "apps.makerspaces.member_card_storage.finalize_photo": "Called only by the tenant-resolved member-card photo route.",
    "apps.card_designs.font_fetch.fetch_family": (
        "Platform card-font library: writes only shared font objects and CardFont rows, never tenant data."
    ),
    "apps.makerspaces.member_card_storage._release": "Reached only through the member-card photo route, revoke and the membership purge.",
    "apps.events.services_images.update_image": "Called by the tenant-resolved event image route.",
    "apps.events.services_series_images.remove_image": "Called by the tenant-resolved event series image route.",
    "apps.events.services_series_images.update_image": "Called by the tenant-resolved event series image route.",
    "apps.events.services_event_details.update_event": (
        "Runs inside the tenant-resolved admin event route's transaction; it can clear "
        "image_key when an occurrence stops overriding its series template."
    ),
    "apps.hardware_requests.direct_loan_returns.validate_evidence_upload": "Runs inside the guarded direct-loan return transaction.",
    "apps.hardware_requests.handover_workflow.issue_request": "Runs inside the request route's tenant transaction.",
    "apps.hardware_requests.return_workflow.return_items": "Runs inside the request route's tenant transaction.",
    "apps.machines.public_printer_service.submit_request": "Runs inside the public-slug printer request route.",
    "apps.machines.services.attach_document": "Runs inside the model-resolved machine document route.",
    "apps.machines.services.remove_document": "Runs inside the model-resolved machine document route.",
    "apps.machines.services.remove_image": "Runs inside the model-resolved machine image route.",
    "apps.machines.services.update_image": "Runs inside the model-resolved machine image route.",
    # Release 2 L12: the one machine job flow's file staging, promotion and attachment.
    "apps.machines.job_files.stage_job_file": "Runs inside the public-slug job upload route.",
    "apps.machines.job_files.validate_job_object": "Runs inside finalize_file, under the job route's tenant transaction.",
    "apps.machines.job_files.attach_job_file": "Runs inside the public-slug job submit and the member resubmit routes.",
    "apps.machines.service_storage_attach._validated": "Runs inside finalize_file, under the request route's tenant transaction.",
    "apps.maintenance.services_documents.delete_log_document": "Runs inside the model-resolved maintenance document route.",
    "apps.maintenance.services_documents.finalize_log_document": "Runs inside the model-resolved maintenance document route.",
    "apps.makerspaces.lifecycle_storage._delete_public_image_keys": "Tenant purge is an express source-gate exclusion.",
    "apps.card_designs.templates_files._store": "Runs inside the template and artwork import routes, which resolve their tenant before storing.",
    "apps.devices.services_adapter_artifacts._upload": "Runs inside the adapter media routes (device or staff), which resolve their tenant first.",
    "apps.devices.services_adapter_artifacts.complete": "Runs inside the adapter media routes (device or staff), which resolve their tenant first.",
    "apps.events.programme.cover_finalize._discard": "Failed-conversion cleanup inside the tenant-resolved event and series cover routes.",
    "apps.events.programme.cover_finalize.convert_to_webp": "Called by the tenant-resolved event and event-series cover image routes.",
    "apps.events.services_deletion.delete_draft": "Runs inside the tenant-resolved admin event route; the cover is released after commit.",
    "apps.machines.type_documents.attach": "Runs inside the tenant-resolved machine type setup route.",
    "apps.machines.type_documents.presign": "Runs inside the tenant-resolved machine type setup route.",
    "apps.machines.type_documents.remove": "Runs inside the tenant-resolved machine type setup route.",
    "apps.makerspaces.account_profile_purge.purge_account_profile": (
        "Account-level purge of one person's own profile images; the account is global, not tenant-owned."
    ),
    "apps.makerspaces.member_card_storage._write_photo": "Reached only through the member-card photo route and the join-photo copy, both tenant-resolved.",
    "apps.makerspaces.membership_join_fields.apply_join_photo": "Runs after commit inside the tenant-resolved join and card-issue routes.",
    "apps.makerspaces.membership_join_fields.presign_join_photo": "Called by the tenant-resolved admission route.",
    "apps.makerspaces.profile_images._release": "Reached only through the authenticated member profile image route and the account purge.",
    "apps.warranty.services.finalize_document": "Runs inside the model-resolved warranty document route.",
    "apps.warranty.services.presign_document": "Runs inside the model-resolved warranty document route.",
    "apps.operations.report_delivery_storage.delete_report_object": (
        "Reached only inside run_report_schedules' skip-and-count tenant boundary, the "
        "tenant-resolved schedule delete route and the reports module purge."
    ),
    "apps.tenant_migration.tenant_dump_cleanup.cleanup_refused_tenant_dump_artifacts": (
        "Deletes only private Lane D coordination artifacts after a refused run."
    ),
    "apps.tenant_migration.tenant_dump_publication._delete_unpublished": (
        "Post-commit cleanup of a refused Lane D coordination artifact."
    ),
    "apps.tenant_migration.tenant_dump_publication._discard_failed_registration": (
        "Fail-closed cleanup of an unpublished Lane D coordination artifact."
    ),
    "apps.tenant_migration.tenant_dump_publication.register_unpublished_artifact": (
        "Offline Lane D sealing writes only a private publication-staging object."
    ),
    "apps.tenant_migration.services_export_job.run_migration_export_job": (
        "The migration export lifecycle owns source_archive_write while uploading."
    ),
    "apps.hardware_requests.replay_execute.execute": (
        "Replay Station boundary spans external finalization; live checks assert the gate in "
        "both transactions."
    ),
    "apps.hardware_requests.replay_prepare._upload_again": (
        "Called inside replay prepare's Station-resolved source-gate boundary."
    ),
    "apps.hardware_requests.self_checkout_contact.issue_upload": (
        "Called only by the public self-checkout evidence views behind the tenant-resolved "
        "source-gate assertion (signed-in and account-less paths, #95)."
    ),
    "apps.evidence.services_upload.issue_upload": (
        "Called only by the staff upload-URL and kiosk evidence-prepare views, both behind "
        "the authenticated late source-gate assertion; the kiosk view also asserts it."
    ),
}
