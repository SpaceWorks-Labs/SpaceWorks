"""Use the installed pgcrypto namespace without relocating provider extensions."""
import re
from django.db import migrations

# Reviewed source vocabulary frozen with this migration; no runtime catalogue import.
APPLICATION_FUNCTIONS = ['accounts_guard_context', 'accounts_guard_walk_in_transition', 'accounts_membership_constraint', 'accounts_validate_memberships', 'apiclients_reject_import_approval_mutation', 'audit_reject_mutation', 'audit_rotation_event_state_order_guard', 'audit_signing_key_lifecycle_guard', 'audit_verification_event_order_guard', 'backup_archive_freeze_fields_guard', 'backup_artifact_ledger_guard', 'backup_b1_columns_changed', 'backup_b1_commitment_matches', 'backup_b1_enforce_reservations', 'backup_b1_fence_continuity_guard', 'backup_b1_frame', 'backup_b1_install_reservation_trigger', 'backup_b1_merge_owns_component', 'backup_b1_merge_write_guard', 'backup_b1_reject_pending_makerspace_materialization', 'backup_b1_reservation_state_guard', 'backup_b1_restore_component_guard', 'backup_b1_restore_operation_guard', 'backup_b1_staff_shell_restore', 'backup_component_guard', 'backup_component_recipient_guard', 'backup_guard_database_identity_mutation', 'backup_managed_binding_immutable', 'backup_reject_reservation_mutation', 'backup_run_freeze_fields_guard', 'backup_runcoverage_freeze_fields_guard', 'booking_website_integrity', 'bookings_departure_tenant_guard', 'bookings_reject_checkin_mutation', 'bookings_reject_departure_mutation', 'boxes_qrscanevent_reject_mutation', 'boxscan_reject_mutation', 'devices_command_identity_guard', 'devices_event_append_only', 'devices_label_claim_guard', 'devices_label_result_guard', 'devices_printer_consumption_guard', 'devices_printer_job_guard', 'encryption_prevent_key_delete', 'encryption_prevent_pii_fence_delete', 'encryption_prevent_pii_global_fence_delete', 'event_website_integrity', 'event_website_owner_window', 'event_website_wall_start', 'events_guard_artwork', 'events_guard_certificate_mutation', 'events_guard_layout_snapshot', 'events_guard_template_revision', 'events_reject_checkin_mutation', 'events_reject_feedback_response_mutation', 'events_template_ownership', 'evidence_photo_key_reservation', 'evidence_receipt_guard', 'evidence_receipt_key_lock', 'evidence_reject_mutation', 'hardware_requests_return_records_reject_mutation', 'machine_kernel_reject_mutation', 'machine_status_since_wp4', 'maintenance_reject_log_mutation', 'membership_vouch_immutable', 'notification_contract_module_removed', 'notification_contract_tenant_guard', 'operations_report_rollup_reject_mutation', 'payments_document_guard', 'payments_due_date_guard', 'payments_manual_refund_guard', 'payments_manual_settlement_guard', 'payments_payment_terminal_guard', 'pii_assert_mapped_write_allowed', 'pii_bloom_contains', 'pii_fence_booking', 'pii_fence_booking_departure', 'pii_fence_email_log', 'pii_fence_event_registration', 'pii_fence_hardware_request', 'pii_fence_machine_service_request', 'pii_fence_manual_print_log', 'pii_fence_membership_application', 'pii_fence_notification_contract', 'pii_fence_print_request', 'pii_fence_printer_job', 'printing_filament_adjustment_reject_mutation', 'service_request_consumption_reject_mutation']



def rewrite(apps, schema_editor, *, reverse=False):
    from psycopg2 import sql
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT n.nspname FROM pg_extension e
            JOIN pg_depend d ON d.refclassid='pg_extension'::regclass AND d.refobjid=e.oid
            JOIN pg_proc p ON d.classid='pg_proc'::regclass AND d.objid=p.oid
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE e.extname='pgcrypto' AND p.proname='digest'
              AND pg_get_function_identity_arguments(p.oid)='bytea, text'
        """)
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise RuntimeError("An executable pgcrypto digest(bytea,text) namespace is required.")
        namespace = rows[0][0]
        if namespace == "public":
            return
        # Only reviewed application functions owned by the migration principal are rewritten. Extension
        # functions and unrelated provider schemas are never modified.
        cursor.execute("""
            SELECT pg_get_functiondef(p.oid) FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.prokind='f'
              AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)
              AND p.proname=ANY(%s)
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass
                              AND d.objid=p.oid AND d.deptype='e')
        """, [APPLICATION_FUNCTIONS])
        definitions = cursor.fetchall()
        qualified = sql.Identifier(namespace).as_string(cursor.connection) + ".digest("
        pattern = re.escape(qualified) if reverse else r'(?:public|"public")\.digest\s*\('
        target = "public.digest(" if reverse else qualified
        for (definition,) in definitions:
            changed = re.sub(pattern, lambda match: target, definition)
            if changed != definition:
                cursor.execute(changed)


def forwards(apps, schema_editor):
    rewrite(apps, schema_editor)


def backwards(apps, schema_editor):
    rewrite(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [("backup", "0027_managed_coordination")]
    operations = [migrations.RunPython(forwards, backwards)]
