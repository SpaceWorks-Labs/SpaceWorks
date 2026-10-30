# Recovery and tenant migration source map

This is the recovery reference linked by [SOURCE-MAP-APPS.md](SOURCE-MAP-APPS.md).
Update it with code moves; the repository tree remains authoritative.

- `backend/apps/backup/` — deployment backup + restore (Phase 5A; one platform-readable component since
  P1b). `age_recipients.py` owns canonical age keys and the platform recipient every archive uses;
  `compound_archive.py` captures the single readable main; `outer_manifest.py` owns the signed v2
  manifest, `artifact_ledger.py` + `models_artifact_ledger.py` own the durable artifact/component rows, and
  `artifact_protocol.py`/`promotion.py`/`reconciliation.py` own staged upload and the single availability
  transaction. `services.py` is the stable barrel over archive/access/lease/run lifecycle modules;
  `models_runs.py` + `runs.py` own scheduled-run cohort and coverage proofs, while `services_runs.py`
  orchestrates their serialized builds. Offsite destinations: `models_offsite.py` (destination +
  upload journal), `offsite_client.py` (S3 byte primitives), `offsite_enqueue.py` (eligibility + journal rows), `offsite_push.py` (fan-out + read-back
  verification), `offsite_retention.py`, `offsite_reverify.py` (periodic re-read), `offsite_restore.py` (create-only rehydration),
  `tasks_offsite.py`, `views_offsite.py`, `services_offsite.py` (shared API/admin retirement and probes)
  and the `fetch_offsite_archive` command. `views_backup_status.py` is the read-only "Last backup" line
  a makerspace's managers see (there is no `backup` module key any more).
  `archive_metadata.py` owns stable build/settings manifest facts;
  `backup_control_preflight.py` is the restore validator behind the `restore_preflight.py`
  compatibility surface and refuses a legacy partial archive. Archive builder, `restore_diff`, the global quarantine
  `middleware.py` + `route_policy.py`, `recovery.py`, `object_restore.py`,
  `operation_lock.py`, and the privileged host scripts (`scripts/restore.sh`, `scripts/import-backup.sh`)
  own verified archive recovery independently of release deployment. Project JWT classes (`accounts/tokens.py`, `token_guard.py`) stamp
  `auth_generation`. The `host_*` modules own H1's marker, consume-only capability socket,
  signed grant, run ledger, supervisor and atomic pointer; `database_grants.py` is its independent
  PostgreSQL role boundary. `cloud_environment.py` captures host-rendered Cloud Compose interpolation into
  durable static configuration without consulting later ambient shells; only the root-only
  `scripts/init-cloud-environment.py` renderer invokes Compose.
  **Per-space backup and restore (P1b B2):** `space_backup_schedule.py` (nightly one-space archives and
  the one schedule view); `space_restore_plan.py` (what a restore replaces/keeps, the archive reader,
  raw fixture rows), `space_restore_graph.py` (on_delete resolution of references into removed rows,
  #113 blocking), `space_restore_users.py` (account re-attribution and re-scrub),
  `space_restore_apply.py` (the one-transaction replacement), `space_restore_objects.py` (bytes under
  original keys), `space_restore_preview.py` (read-only preview + live fingerprint),
  `space_restore_staging.py` (open with the server key, #50b), `space_restore_services.py` (journal
  transitions + audit), `space_restore_runner.py` (safety backup, gate, apply), `space_restore_notifications.py`
  (console notice + manager email), `tasks_space_restore.py`, `models_space_restore.py`
  (`MakerspaceRestoreOperation`), `views_space_restore.py` + `serializers_space_restore.py` (API, routed by
  `admin_api/urls_space_restore.py`), `admin_space_backup.py` + `admin_deployment.py` (the `/control/`
  console). The host marker (`host_marker.py`) is v3 without readiness lists.

- `backend/apps/tenant_migration/` — per-makerspace migration, managed → self-host (Phase 5B), in
  `SEPARABLE_APPS`. `source_gate.py` + `gate_locks.py`/`gate_runtime.py`/`gate_policy.py`/`middleware.py`/
  `task_gate.py` (the write-drain lock protocol and its AST coverage guards in `source_gate_guards.py`, with
the lifecycle/object-mutation half in `source_gate_object_guards.py`);
  `archive_envelope.py` + `object_export.py` (streamed into `age`); `admission.py` (the source-superadmin
  closure approval); `materialization.py` (+ `materialization_rows.py`) + `raw_repository.py` + `row_planning.py`
  (+ `row_values.py`, `row_references.py`)/`row_dispositions.py` (one-shot insertion); `services_import_job.py` re-exports `services_import_run.py`
  (requester checks and attempt-fenced execution) with `import_run_lock.py` holding the dedicated
  advisory-lock connection; `target_projection.py` (barrel over `target_projection_{types,fields,rows,references}.py`)
  + `unique_values.py` (barrel: the rules dict is
  `unique_values_core.py`, the disposition/policy types `unique_values_policy.py`) + `closure_references.py`;
  `tenant_dump_model_catalog.py` + `tenant_dump_field_snapshot.py` +
  `tenant_dump_authority.py` (public barrel over literal `tenant_dump_authority_entries.py`
  and domain supplements)/`tenant_dump_catalog.py` (Lane D's deny-by-default source catalog), and
  `tenant_dump_source_projection.py` (single-makerspace raw rows plus decision-22 grant closure);
  `tenant_dump_builder.py` (Lane D's migrated scratch → verified custom-dump orchestrator), with
  `tenant_dump_database.py`, `tenant_dump_graph.py`, `tenant_dump_raw.py`, `tenant_dump_sql.py` and
  `tenant_dump_verification.py` owning run-scoped databases, actual-row FK ordering/nullable cycles,
  reviewed raw columns, fence/closure SQL and restored-candidate verification respectively;
  `tenant_dump_sequences.py` owns Lane D's exact empty/non-empty sequence state;
  `tenant_dump_machine_types.py` resolves only fingerprint-identical global built-ins, while
  `tenant_dump_objects.py` packages immutable staged object bytes without live-storage reads;
  `tenant_dump_capture.py` + `tenant_dump_capture_database.py` freeze the full exported-snapshot database
  and exact object bytes before `source_gate_release.py` performs the fenced `copy_capture` release;
  `tenant_dump_staging.py` + `tenant_dump_database_cleanup.py` own marker-guarded crash cleanup;
  `tenant_dump_cleanup.py` retries refused unpublished-object deletion from its durable capture-row key;
  `tenant_dump_derivation.py` derives and seals output only from that capture;
  `tenant_dump_pii.py` binds raw mapped-column mode findings and ciphertext AAD identities;
  `tenant_dump_key_inventory.py` freezes and exact-set checks source-broker key facts, while
  `tenant_dump_dek_protocol.py`/`tenant_dump_dek_helper.py`/`tenant_dump_deks.py` keep plaintext DEKs inside
  the bounded child operation and emit only the tenant-recipient ciphertext;
  `tenant_dump_recipients.py` validates the one-shot `--recipient` keys and keeps `outer_recipients`
  (tenant keys plus the platform key) and `tenant_dek_recipients` (tenant keys only) distinct, and
  `tenant_dump_envelope.py` owns the declared key-member presence/absence ledger plus streaming outer seal;
  `tenant_dump_target.py` binds D5's pre-destructive identity proof to reconstruction, with
  `tenant_dump_target_identities.py` enforcing read-only mode-0600 tenant mounts,
  `tenant_dump_target_protocol.py`/`tenant_dump_target_helper.py`/`tenant_dump_target_deks.py` owning the
  key-free parent plus bounded target decrypt/rewrap child, and `tenant_dump_target_readiness.py` rebuilding
  target search derivations and authenticated readiness;
  `tenant_dump_manifest.py` and `tenant_dump_lineage.py` bind D4 envelope facts and parent/policy digests;
  `tenant_dump_publication.py` owns lineage/money revalidation, refusal cleanup and the atomic
  pending-to-published/download transition; `tenant_dump_audit_anchors.py` supplies the fail-closed
  external-anchor absence proof;
  `tenant_restore_orchestrator.py` is the D7 §5.4 ordered target-restore spine over H1;
  `tenant_restore_activation.py` owns crash-safe pointer/marker re-entry and writer restart, with
  `tenant_restore_preflight.py`, `tenant_restore_database*.py`, `tenant_restore_sibling.py`,
  `tenant_restore_pgpass.py`, `tenant_restore_pointer.py` and `tenant_restore_scheduler.py` owning
  topology/privilege/lifecycle/credential-minimization/CAS/callback refusal boundaries;
  `tenant_restore_target_state.py`, `tenant_restore_objects.py`, `tenant_restore_api_clients.py`,
  `tenant_restore_superadmin.py` and `host_credential_delivery.py` own target-import gating, pre-ledgered
  object effects, approved authority reset and durable one-time credential delivery;
  `verification.py` (pre-commit), audit-reference domains behind the `audit_references.py` barrel, and
  `target_cutover.py` (pre-activation + `IMPORTING → ACTIVE`);
  `receipts.py`/`receipt_crypto.py`/`cutover.py` (signed single-use handoff); `views_*.py` (superadmin REST).
