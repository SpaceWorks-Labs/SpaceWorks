#!/usr/bin/env bash
# A pinned installer stages new host tooling separately from private installation state.
# Copy only the runtime bundle after the database backup; preserve every replaced file.
host_bundle_files() {
  HOST_BUNDLE_FILES=(
    VERSION setup.sh install.sh setup.ps1
    scripts/uninstall.sh scripts/init-cloud-environment.py
    deploy/contracts/programmes.json
    scripts/cloud_setup/__init__.py scripts/cloud_setup/answers.py
    scripts/cloud_setup/bootstrap.py scripts/cloud_setup/cli.py
    scripts/cloud_setup/completion.py scripts/cloud_setup/database_probe.py
    scripts/cloud_setup/email_config.py scripts/cloud_setup/environment.py
    scripts/cloud_setup/errors.py scripts/cloud_setup/free_profile.py
    scripts/cloud_setup/host_commit.py scripts/cloud_setup/interactive.py
    scripts/cloud_setup/kubernetes.py scripts/cloud_setup/native.py
    scripts/cloud_setup/private_files.py scripts/cloud_setup/recipes.py
    scripts/cloud_setup/render.py scripts/cloud_setup/secret_files.py
    scripts/cloud_setup/secrets.py scripts/cloud_setup/service_probes.py
    scripts/cloud_setup/storage_probe.py scripts/cloud_setup/validation.py
    scripts/installer/answers.py
    scripts/installer/answers.sh
    scripts/installer/bundle-transaction.sh
    scripts/installer/capacity.sh
    scripts/installer/capacity.py scripts/installer/capacity-metrics.py
    scripts/installer/completion.sh scripts/installer/environment-continuity.sh
    scripts/installer/privileged-target.sh scripts/installer/probe-bundle.py
    scripts/installer/probe-common.py scripts/installer/probe-services.py
    scripts/installer/probe-storage.py scripts/installer/probe-integrations.py
    scripts/installer/probe-external.py scripts/installer/outside-services.sh scripts/installer/outside-checks.sh
    scripts/installer/external-db-dump.py scripts/installer/external-restore-db.py
    scripts/switch-services.sh
    scripts/installer/restore-terminal.py scripts/installer/retention-receipts.py
    scripts/installer/retention.sh
    scripts/installer/retention-run.sh
    scripts/installer/retention-schedule.py scripts/installer/retention-schedule.sh
    scripts/installer/compose-capabilities.py
    scripts/installer/compose-capabilities.sh
    scripts/installer/compose-plugin.py
    scripts/installer/credential.py
    scripts/installer/host-paths.sh
    scripts/installer/host-preflight.sh
    scripts/installer/import-environment.sh
    scripts/installer/import-journal.py
    scripts/installer/install-finish.sh
    scripts/installer/install-runtime.sh scripts/installer/install-entry.sh
    scripts/installer/key-backfill-probe.py
    scripts/installer/key-backfill.sh
    scripts/installer/key-format.py
    scripts/installer/legacy-identity.py
    scripts/installer/linux-dependencies.sh
    scripts/installer/managed-files.py
    scripts/installer/pre-h1.sh
    scripts/installer/private_files.py
    scripts/installer/project-name.py
    scripts/installer/record-snapshot.py
    scripts/installer/release-fetch.py
    scripts/installer/restore-owner.sh
    scripts/installer/restore-work.sh
    scripts/installer/retention.py
    scripts/installer/runtime-probes.py
    scripts/installer/setup-lock.sh
    scripts/installer/setup-scan.sh
    scripts/installer/frontend-choice.sh
    scripts/installer/setup-state.sh
    scripts/installer/state.py
    scripts/installer/uninstall-admission.py
    scripts/installer/uninstall-files.py
    scripts/installer/update-backup.sh
    docker-compose.prod.yml docker-compose.cloud.yml docker-compose.free.yml deploy/cloud/free.env.example
    docker/compose.build.yml docker/compose.tls.yml docker/compose.saas.yml
    docker/compose.api-only.yml docker/compose.api-only-edge.yml docker/compose.external-storage.yml
    docker/compose.external-db.yml docker/compose.external-redis.yml docker/compose.no-redis.yml
    docker/compose.control-tunnel.yml
    deploy/Caddyfile deploy/Caddyfile.saas deploy/Caddyfile.saas-install frontend/nginx.conf
    deploy/nginx.api-only.conf deploy/storage.caddy deploy/storage-disabled.caddy
    deploy/control-plane-false.caddy deploy/control-plane-true.caddy
    deploy/control-tunnel-off.caddy deploy/control-tunnel-on.caddy
    frontend/docker/control-plane-allowlist.sh frontend/docker-entrypoint.d/40-control-plane.sh
    scripts/compose-deployment.sh scripts/setup-question-input.sh scripts/setup-questions.sh
    scripts/setup-area-questions.sh scripts/setup-areas-json.sh scripts/module-area-selection.sh scripts/module-legacy-selection.sh
    scripts/setup-write-environment.sh scripts/setup-proxy-config.sh scripts/update-rollback.sh scripts/apply-settings.sh scripts/control-plane-settings.sh
    scripts/bundled-database-url.py scripts/cleanup-run-once.sh scripts/configure-compose-wrapper.py
    scripts/host-capability.py scripts/import-backup.sh
    scripts/init-host-orchestration.sh scripts/install-runner.sh scripts/runner-release.py scripts/install-host-bundle.sh
    scripts/install-owner.sh scripts/module-selection.sh scripts/restore.sh scripts/retire-update-polling.sh scripts/retire-update-tombstone.sh
    scripts/select-main-release.py scripts/setup-first-run.sh
    scripts/setup-host-orchestration.sh scripts/spaceworks-compose.sh scripts/spaceworks-repository.sh
    scripts/update-lock.sh scripts/update.ps1 scripts/update.sh scripts/validate-compose-wrapper.py
    scripts/update-release-bundle.sh scripts/release-host-bundle.py scripts/update-proxy-edges.sh
    scripts/restore-database-identity.sh scripts/restore-database-identity.py scripts/restore-database-ops.sh
  )
}

validate_host_bundle() {
  local source_root="$1" relative
  host_bundle_files
  # Refuse incomplete archives before replacing any file.
  for relative in "${HOST_BUNDLE_FILES[@]}"; do
    [[ -f "$source_root/$relative" ]] || die "The pinned archive lacks $relative."
  done
}

install_staged_host_bundle() {
  local source_root="$1"
  [[ "$source_root" != "$ROOT" ]] || die "Release tooling must be staged outside the existing install."
  validate_host_bundle "$source_root"
  source "$(dirname "${BASH_SOURCE[0]}")/installer/bundle-transaction.sh"
  RETIRED_HOST_FILES=(scripts/install-auto-update.sh scripts/install-auto-update.ps1
    scripts/update-rollback-host.sh scripts/filter-main-releases.py docker/compose.single.yml)
  HOST_CONFIG_BACKUP_DIR="$ROOT/backups/host-config-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  bundle_path_safe backups || die 'The private backup directory is redirected.'
  mkdir -p "$ROOT/backups" || return
  chmod 700 "$ROOT/backups" || return
  snapshot_host_configuration || die 'Cannot snapshot the previous host configuration; no bundle was applied.'
  if ! apply_host_bundle "$source_root"; then
    rollback_host_configuration || die 'Host-file rollback failed; keep writers stopped and recover the private host-config snapshot.'
    die 'Host bundle apply failed; the previous files and records were restored.'
  fi
  say "Installed pinned host runtime files; previous files are in $HOST_CONFIG_BACKUP_DIR."
}
