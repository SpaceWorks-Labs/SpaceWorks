# Deployment and backup source map

- `scripts/install-runner.sh` - optional Linux/systemd GitHub Actions runner registration/removal,
  silent short-lived tokens, install-owner service, `spaceworks-prod` label and final GitHub operator steps.
  `scripts/runner-release.py` selects the latest host architecture asset and validates published SHA-256
  checksums before extraction. The runner `.env` records `SPACEWORKS_DIR`.
- `.github/workflows/release.yml` - image and GitHub release publication followed by an opt-in `deploy`
  job on `[self-hosted, spaceworks-prod]`, restricted to main and `SPACEWORKS_DEPLOY=true`. It invokes
  the installed updater for exactly `needs.prepare.outputs.version`, with no checkout or action steps.
- `scripts/update.sh` - portable lock, validated exact/newest GitHub main-release selection, pre-update SQL backup,
  pinned-image deployment, readiness, version marker and automatic application-image rollback.
  `scripts/install-owner.sh` preserves install-owner/sudo re-entry. `scripts/setup-first-run.sh` owns
  guided first-run settings and private `.env` creation. `scripts/spaceworks-compose.sh` validates with
  host Python 3.10+ when available, otherwise in the backend image under the caller's UID/groups.
  Successful runs remove completed migration, orchestration and bucket-creation containers; failures
  preserve them for inspection. Database recovery remains a separate operation.
  `scripts/setup-proxy-config.sh` writes the operator-managed nginx configuration for own-proxy
  HTTPS and prints DNS, Certbot, install and reload steps. `scripts/setup-questions.sh` owns
  the hosting-to-runner questionnaire, including control-plane, MFA and provider choices.
- `scripts/install-host-bundle.sh` - stages an explicit host runtime bundle on installer upgrades,
  retaining replaced files in `backups/host-config-*`. The updater first verifies its database dump
  and pulls the new backend image, then replaces the bundle and refreshes Compose trust records.
  `scripts/retire-update-polling.sh` removes the former update cron without removing other jobs;
  `scripts/retire-update-tombstone.sh` removes only the retired app label from host configuration.

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

- Lane F ops: `operations/route_metrics.py`, `config/gunicorn_metrics*.py` own
  bounded multi-process HTTP instrumentation; `operations/control_storage.py` and
  `templates/admin/storage.html` render existing storage totals. `config/web_analytics.py`
  validates optional origins. `charts/spaceworks` supplies H1-preserving deployment,
  migration-hook, service and ingress manifests. Operational contracts are in
  `docs/monitoring-and-analytics.md` and `docs/helm.md`; installer paths are unchanged.
