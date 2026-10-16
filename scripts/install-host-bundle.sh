#!/usr/bin/env bash
# A pinned installer stages new host tooling separately from private installation state.
# Copy only the runtime bundle after the database backup; preserve every replaced file.
host_bundle_files() {
  HOST_BUNDLE_FILES=(
    VERSION setup.sh install.sh setup.ps1
    docker-compose.prod.yml docker-compose.cloud.yml
    docker/compose.build.yml docker/compose.tls.yml docker/compose.saas.yml
    docker/compose.api-only.yml docker/compose.api-only-edge.yml docker/compose.external-storage.yml
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
    scripts/restore-database-identity.sh scripts/restore-database-identity.py
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
  local source_root="$1" destination backup relative temporary
  [[ "$source_root" != "$ROOT" ]] || die "Release tooling must be staged outside the existing install."
  validate_host_bundle "$source_root"
  backup="$ROOT/backups/host-config-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  HOST_CONFIG_BACKUP_DIR="$backup"
  mkdir -p "$ROOT/backups"
  chmod 700 "$ROOT/backups"
  for relative in "${HOST_BUNDLE_FILES[@]}"; do
    destination="$ROOT/$relative"
    mkdir -p "$(dirname "$destination")" "$(dirname "$backup/$relative")"
    [[ ! -f "$destination" ]] || cp -p "$destination" "$backup/$relative"
    temporary="$(mktemp "$(dirname "$destination")/.deploy-bundle.XXXXXX")"
    cp -p "$source_root/$relative" "$temporary"
    mv -f -- "$temporary" "$destination"
  done
  for relative in scripts/install-auto-update.sh scripts/install-auto-update.ps1 \
    scripts/update-rollback-host.sh scripts/filter-main-releases.py docker/compose.single.yml; do
    if [[ -f "$ROOT/$relative" ]]; then
      mkdir -p "$(dirname "$backup/$relative")"
      mv -- "$ROOT/$relative" "$backup/$relative"
    fi
  done
  say "Installed pinned host runtime files; previous files are in $backup."
}
