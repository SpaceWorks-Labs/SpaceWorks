#!/usr/bin/env bash
# Called only with operation.lock held and the signed preflight already accepted.
install_import_environment() {
  local backend_container
  backend_container="$("${COMPOSE[@]}" ps -q backend)" || return
  HOST_CONFIG_IMAGE="$(docker inspect --format '{{.Image}}' "$backend_container")" || return
  [[ "$HOST_CONFIG_IMAGE" =~ ^sha256:[0-9a-f]{64}$ ]] || die 'Cannot pin the installed configuration tooling.'
  source "$ROOT/scripts/setup-host-orchestration.sh"
  env_backup=".env.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  cp -p -- .env "$env_backup" || return
  chmod 600 "$env_backup"
  # Preserve exact record bytes, owner and permissions, including every overlay.
  docker run --rm --user 0:0 --network none --entrypoint python \
    -v "$OPS_DIR:/ops" -v "$WORK:/work" "$HOST_CONFIG_IMAGE" -c \
    "$(cat "$ROOT/scripts/installer/record-snapshot.py")" snapshot /ops /work/records.json || return
  import_env_applied=1
  python3 "$ROOT/scripts/installer/import-journal.py" begin "$ROOT" "$OPS_DIR" \
    "$WORK" "$env_backup" "$HOST_CONFIG_IMAGE" || return
  install -m 600 "$WORK/target.env" .env || return
  refresh_compose_config || return
  deployment_services || return
  "${COMPOSE[@]}" up -d --no-deps --force-recreate "$APP_SERVICE" "${WORKER_SERVICES[@]}" || return
}

rollback_import_environment() {
  [[ "${import_env_applied:-0}" == 1 ]] || return 0
  if [[ "${import_env_ambiguous:-0}" == 1 ]]; then
    "${COMPOSE[@]}" stop "$APP_SERVICE" "${WORKER_SERVICES[@]}" >/dev/null 2>&1 || true
    echo 'Restore registration may have committed; environment rollback was refused. Keep writers stopped and inspect the retained restore intent and private recovery journals.' >&2
    return 1
  fi
  install -m 600 "$env_backup" .env || return
  docker run --rm --user 0:0 --network none --entrypoint python \
    -v "$OPS_DIR:/ops" -v "$WORK:/work" "$HOST_CONFIG_IMAGE" -c \
    "$(cat "$ROOT/scripts/installer/record-snapshot.py")" restore /ops /work/records.json || return
  if ! "${COMPOSE[@]}" up -d --no-deps --force-recreate "$APP_SERVICE" "${WORKER_SERVICES[@]}"; then
    "${COMPOSE[@]}" stop "$APP_SERVICE" "${WORKER_SERVICES[@]}" || true
    echo 'Continuity rollback could not restart writers; leave them stopped and recover from the private environment backup.' >&2
    return 1
  fi
  [[ ! -e "$ROOT/.spaceworks-import-pending.json" ]] || \
    python3 "$ROOT/scripts/installer/import-journal.py" clear "$ROOT" "$OPS_DIR" || return
}

recover_import_environment() {
  [[ -e "$ROOT/.spaceworks-import-pending.json" ]] || return 0
  local transport
  transport="$(mktemp)" || return
  chmod 600 "$transport"
  python3 "$ROOT/scripts/installer/import-journal.py" read "$ROOT" "$OPS_DIR" > "$transport" || {
    rm -f "$transport"; return 1;
  }
  { IFS= read -r -d '' WORK; IFS= read -r -d '' env_backup; IFS= read -r -d '' HOST_CONFIG_IMAGE; } < "$transport"
  rm -f "$transport"
  import_env_applied=1
  rollback_import_environment || return
  import_env_applied=0
  rm -rf -- "$WORK"
}
