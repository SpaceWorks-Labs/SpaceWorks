# Lane 7c progress

## Completed

- Step 0 reviewed the actual 7a tree, actual sibling 7b interfaces, parent plan/review,
  HANDOVER-CODEX section 7 and relevant invariants. Review is saved locally at the
  gitignored path listed below; coordinator must copy it to the requested MAIN path.
- Added LabelPrintCommand and immutable LabelPrintResult receipts, migration and DB
  guards; read-only admin; current-key/device/tenant ownership checks.
- Added MANAGE_QR staff send/reprint and paginated history; freezes DRAFT batches
  transactionally; item additions/relabels now lock and reject non-DRAFT batches.
- Asset generation locks its RBAC-scoped makerspace before product/batch, avoiding
  the newly exposed inversion with a later managed quota lock; race test added.
- Added signed ZIP content/result routes with exact registry and OpenAPI schemas.
  Existing qr_zip renderer is unchanged; no bytes, secrets or objects are persisted.
- Integrated label dispatch/retries/cancellation in copies of 7b delivery services.
  Only label deltas should be applied over the coordinator's final 7b versions.
- Added result replay receipts, fixed allowlisted printer messages, typed audit and
  DeviceEvent provenance, export/User/FK/snapshot/catalog/authority/unique/purge rules.
- Documented the label contract in docs/device-label-commands.md and SOURCE-MAP.

## Remaining for coordinator

- Integrate 7b FIRST. This branch intentionally does not duplicate its models, routes,
  settings or 0002 migration. It is not independently bootable until that lands.
- Merge shared barrel additions (models/admin/events/routes/URLs, export registries,
  authority expectations, snapshot registry, projection and purge collector). Keep
  7b event choices before the new label choices, matching migration 0003.
- Recompute CATALOG_SCHEMA_SHA256 after combining 7b+7c (and any concurrent models);
  this lane cannot bless a model graph whose prerequisite models are absent.
- Copy stage1-p7c.md to MAIN docs/plans/2026-09-03-forward-plan/reviews/.
- Regenerate frontend/openapi-schema.json and frontend/src/generated/api.ts.
- Run isolated DB tests listed below plus operations QR, data_export, tenant_migration
  guards, device/printer regressions, system/migration/schema checks and full suite.
- Run tombstone tests in the repository's eleven-app tombstone profile.
- Complete the coordinator's review gate. Nested CLI review is blocked in this sandbox.

## Verification performed (no DB tests executed)

- codex doctor: config/CODEX_HOME unavailable; required provider unreachable.
- python --version: Python 3.14.7. Django import fails: no local Django package.
- git diff --check: no whitespace errors in tracked changes.
- Python ast.parse over changed Python files: no syntax errors.
- Static field-set comparison: both model/migration/export/tenant snapshots agree.
- File-size inspection: every changed file is under 300 lines.
- Read-only git status/diff and sibling comparison: no staging/commit/merge/push.

## Migration

- backend/apps/devices/migrations/0003_label_commands.py depends on
  devices.0002_printer_jobs (actual sibling 7b leaf), operations.0009_report_schedules
  (actual local leaf), and swappable AUTH_USER_MODEL. Adds both label tables,
  request/operation/terminal constraints, immutable DB guards and event choices.

## Deliberately skipped / decisions / outside-scope observations

- No owner product decision needed; unresolved door/agent/printer packaging remains
  deferred exactly as the parent plan specifies. Staff UI belongs to 7d.
- No canonical MODULES.md / INVARIANTS.md edit: those are already >300 lines; the
  lane's hard ceiling forbids touching them without a broad split. New standalone
  documentation carries the complete contract. Coordinator may link/fold it in.
- fields.py derives dispositions from literal classification entries, and ordinary
  FKs remap automatically; no additional fields/closure/discriminator changes needed.
- Reviewed JSON/encryption/report/settings/object/ownership/storage/fanout registries:
  no new JSON, PII, report type, setting, stored artifact, task or module/feature key.
- Outside 7c: qr_zip has no explicit size limit and varies ZIP entry timestamps.
  Preserve its renderer; tests compare SVG contents instead of ZIP timestamps.
- Generated schemas, combined digest, main-checkout copy, database suite and external
  CLI review remain coordinator/environment work, not claimed completed checks.

## Every file created or modified

- LANE-PROGRESS.md
- backend/apps/data_export/classification.py
- backend/apps/data_export/classification_7c.py
- backend/apps/data_export/datasets.py
- backend/apps/data_export/datasets_7c.py
- backend/apps/data_export/references.py
- backend/apps/data_export/references_7c.py
- backend/apps/devices/admin.py
- backend/apps/devices/admin_labels.py
- backend/apps/devices/errors_labels.py
- backend/apps/devices/label_access.py
- backend/apps/devices/migrations/0003_label_commands.py
- backend/apps/devices/migrations/_label_guards.py
- backend/apps/devices/models.py
- backend/apps/devices/models_events.py
- backend/apps/devices/models_labels.py
- backend/apps/devices/route_registry.py
- backend/apps/devices/route_registry_7c.py
- backend/apps/devices/serializers_commands.py
- backend/apps/devices/serializers_labels.py
- backend/apps/devices/services_commands.py
- backend/apps/devices/services_label_commands.py
- backend/apps/devices/services_label_delivery.py
- backend/apps/devices/services_label_events.py
- backend/apps/devices/services_label_results.py
- backend/apps/devices/urls.py
- backend/apps/devices/urls_7c.py
- backend/apps/devices/views_labels.py
- backend/apps/makerspaces/module_purge_collectors_7c.py
- backend/apps/makerspaces/module_purge_collectors_devices.py
- backend/apps/makerspaces/origin_scope_model_lookups.py
- backend/apps/operations/services_qr_assets.py
- backend/apps/tenant_migration/audit_references_meta.py
- backend/apps/tenant_migration/audit_references_meta_7c.py
- backend/apps/tenant_migration/catalog_7c.py
- backend/apps/tenant_migration/references_7c.py
- backend/apps/tenant_migration/references_devices.py
- backend/apps/tenant_migration/target_projection.py
- backend/apps/tenant_migration/target_projection_7c.py
- backend/apps/tenant_migration/tenant_dump_authority_7c.py
- backend/apps/tenant_migration/tenant_dump_authority_supplement.py
- backend/apps/tenant_migration/tenant_dump_field_snapshot.py
- backend/apps/tenant_migration/tenant_dump_model_catalog.py
- backend/apps/tenant_migration/unique_values.py
- backend/apps/tenant_migration/unique_values_7c.py
- backend/tests/devices/helpers_labels.py
- backend/tests/devices/test_label_commands.py
- backend/tests/devices/test_label_concurrency.py
- backend/tests/devices/test_label_data_export.py
- backend/tests/devices/test_label_delivery.py
- backend/tests/devices/test_label_gates.py
- backend/tests/devices/test_label_tenant_migration.py
- backend/tests/operations/test_qr_batch_freeze.py
- backend/tests/tenant_migration/authority_expectations_7c.py
- backend/tests/tenant_migration/test_authority_dispositions_d8.py
- backend/tests/tombstone/test_label_devices_7c.py
- docs/SOURCE-MAP.md
- docs/device-label-commands.md
- docs/plans/2026-09-03-forward-plan/reviews/stage1-p7c.md

## Every new test (coordinator must run)

### backend/tests/devices/test_label_commands.py

- test_first_send_freezes_batch_and_matching_replay_creates_no_second_command
- test_printed_batch_reprint_uses_new_request_id_and_paginated_listing
- test_invalid_batch_does_not_queue
- test_device_kind_and_status_are_enforced
- test_request_id_conflict_for_another_batch
- test_request_id_conflict_for_another_active_label_device
- test_manage_qr_without_manage_devices_can_send_but_device_only_role_cannot
- test_cross_tenant_device_and_batch_are_not_disclosed
- test_request_claim_cannot_be_rewritten_by_queryset_update
- test_unknown_fields_are_rejected_at_staff_boundary

### backend/tests/devices/test_label_concurrency.py

- test_concurrent_duplicate_staff_request_creates_one_command
- test_first_send_serializes_against_relabel
- test_concurrent_same_result_writes_one_receipt_and_one_effect
- test_send_and_asset_generation_keep_tenant_before_batch_lock_order

### backend/tests/devices/test_label_data_export.py

- test_label_model_field_dataset_user_and_reference_catalogs_are_complete
- test_export_contains_label_receipts_and_history_without_stored_bytes
- test_label_purge_deletes_immutable_receipts_before_parents_and_keeps_qr_batch

### backend/tests/devices/test_label_delivery.py

- test_zip_is_exact_existing_svg_batch_with_safe_private_headers
- test_unacknowledged_content_result_and_wrong_token_are_refused
- test_acknowledged_long_print_survives_short_delivery_lease_expiry
- test_success_replay_is_identical_and_conflicting_operation_cannot_finish_twice
- test_retry_receipt_replay_does_not_requeue_or_overwrite_a_later_success
- test_permanent_or_exhausted_failure_is_terminal
- test_late_ack_cannot_cancel_permanent_failure_or_break_result_replay
- test_key_rotation_cannot_reuse_a_previously_acknowledged_label_command
- test_expired_unacknowledged_lease_requeues_then_exhausts
- test_another_signed_device_cannot_fetch_or_report_and_revocation_is_rechecked
- test_purged_batch_cancels_delivery_and_snapshots_cannot_restore_it
- test_purged_acknowledged_batch_commits_cancellation_before_410
- test_result_text_and_unknown_fields_never_enter_receipts_or_logs
- test_result_receipt_is_database_immutable
- test_terminal_label_outcome_is_database_immutable_but_batch_purge_can_null_fk

### backend/tests/devices/test_label_gates.py

- test_module_off_returns_400_on_staff_content_and_results
- test_disabled_label_adapter_is_cancelled_by_generic_poll_and_never_resurrects
- test_source_gate_refuses_all_label_writes_without_creating_receipts
- test_staff_origin_scope_reads_batch_pk_and_device_registry_is_exact
- test_openapi_documents_staff_send_signed_zip_and_idempotent_result

### backend/tests/devices/test_label_tenant_migration.py

- test_label_tenant_catalog_projection_references_and_unique_rules_are_complete
- test_every_imported_command_is_cancelled_and_lease_ownership_cleared
- test_portable_label_history_remaps_live_edges_preserves_receipts_and_never_prints

### backend/tests/operations/test_qr_batch_freeze.py

- test_non_draft_batch_cannot_add_or_relabel_even_with_a_stale_instance
- test_manual_mark_printed_uses_the_same_freeze_boundary_as_device_send

### backend/tests/tenant_migration/test_authority_dispositions_d8.py

- Existing exact authority matrix tests extended by authority_expectations_7c.py.

### backend/tests/tombstone/test_label_devices_7c.py

- test_label_routes_are_absent_when_devices_are_tombstoned
- test_label_schema_and_admin_are_absent_but_history_tables_remain
