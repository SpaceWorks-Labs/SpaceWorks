#!/usr/bin/env bash
# Failed image deployment leaves forward migrations in place; never restore data here.
# This is only the in-flight rollback of a FAILED update to the images that were running when it
# started. It is not a downgrade path: upgrades are forward-only (decision 219g), the updater
# refuses an older target, and a deliberate return to an older version means restoring the
# pre-upgrade backup (docs/install-and-update.md#rolling-back).
rollback_application_images() {
  UPDATE_ROLLBACK_PROVEN=0
  [[ "$previous_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}$ ]] || return 0
  say "Update failed; rolling application containers back to $previous_version."
  export MAKERSPACE_IMAGE_TAG="$previous_version"
  "${COMPOSE[@]}" pull "${IMAGE_SERVICES[@]}" || \
    say "Could not refresh previous images; trying the host's cached copies."
  HOST_CONFIG_IMAGE="$MAKERSPACE_BACKEND_IMAGE:$previous_version"
  if ! install_producer_capability; then
    "${COMPOSE[@]}" stop "$APP_SERVICE" "${WORKER_SERVICES[@]}" || true
    say 'Previous producer proof could not be installed; writers remain stopped.'
    return 1
  fi
  # --no-deps prevents old migrations from being applied to the forward schema.
  if "${COMPOSE[@]}" up -d --no-deps "${ROLLBACK_SERVICES[@]}" && refresh_update_proxy_edges && wait_for_backend; then
    printf '%s\n' "$previous_version" > "$VERSION_FILE" || return
    UPDATE_ROLLBACK_PROVEN=1
    say "Rollback complete: $previous_version is healthy."
    cleanup_run_once_jobs || warn "Could not remove finished rollback jobs."
    say "Database changes remain; backup retained at backups/$backup_name."
  else
    "${COMPOSE[@]}" stop "$APP_SERVICE" "${WORKER_SERVICES[@]}" || true
    say "ERROR: automatic rollback to $previous_version failed."
    say "Restore backups/$backup_name and the previous image tag manually."
    return 1
  fi
}
