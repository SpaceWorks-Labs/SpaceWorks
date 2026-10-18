#!/usr/bin/env bash
# Narrow, versioned transition for a verified published, bundled pre-H1 release.
# Caller holds portable update and operation locks. Unknown layouts fail closed.
transition_pre_h1() {
  [[ ! -e "$ROOT/.spaceworks-transition.json" && ! -L "$ROOT/.spaceworks-transition.json" ]] || \
    die 'An interrupted pre-H1 transition must be recovered from its private backup before any update or module change.'
  [[ ! -f "$OPS_DIR/database-pointer.env" || ! -f "$ROOT/scripts/spaceworks-compose.sh" ]] || return 0
  local current layer stage="" old_identity active_name container image
  current="$(tr -d '[:space:]' < "$ROOT/.spaceworks-version")"
  layer="$(cat "$ROOT/.spaceworks-layer" 2>/dev/null || printf none)"
  [[ "$current" =~ ^[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}$ \
     && "$layer" == none && "$UPDATE_SCRIPT_DIR" != "$ROOT/scripts" \
     && ! -e "$ROOT/.spaceworks-transition.json" ]] || die \
    'Unsupported or interrupted pre-H1 layout. Keep the old release and private data; restore its coordinated backup on a supervised full host before updating.'
  if grep -q '^x-spaceworks-host-orchestration:' "$ROOT/docker-compose.prod.yml"; then
    die 'H1 configuration with a missing wrapper/pointer is a recovery case, not a pre-H1 install. Recover its exact host records; never initialize a guessed pointer.'
  fi
  stage="$(mktemp -d "$ROOT/.spaceworks-legacy.XXXXXX")"
  # Fetch and verify the ACTUAL installed old release, including every Git blob.
  python3 "$UPDATE_SCRIPT_DIR/installer/release-fetch.py" --repository "$SPACEWORKS_REPOSITORY" \
    --version "$current" --destination "$stage" >/dev/null || die 'Cannot verify the installed legacy release.'
  cmp -s "$ROOT/docker-compose.prod.yml" "$stage/runtime/docker-compose.prod.yml" \
    || die 'Legacy Compose differs from the published release; recover with its matching host configuration.'
  [[ ! -e "$OPS_DIR/database-pointer.env" ]] || die 'Partial H1 state exists; use host recovery instead of legacy transition.'
  local legacy=(docker compose --env-file "$ROOT/.env" -f "$ROOT/docker-compose.prod.yml")
  container="$("${legacy[@]}" ps -q backend)" || return
  image="$(docker inspect --format '{{.Config.Image}}' "$container")" || return
  [[ "$image" == "$MAKERSPACE_BACKEND_IMAGE:$current" ]] || die 'Legacy running image is not the proven release.'
  old_identity="$("${legacy[@]}" exec -T backend python -c "$(cat "$UPDATE_SCRIPT_DIR/installer/legacy-identity.py")")" || return
  [[ "$old_identity" =~ ^([A-Za-z_][A-Za-z0-9_$]{0,62})\|[1-9][0-9]*$ ]] || die 'Invalid legacy database identity.'
  active_name="${old_identity%%|*}"
  local configured_database
  configured_database="$(deployment_value POSTGRES_DB)"; configured_database="${configured_database:-makerspace_manager}"
  [[ "$active_name" == "$configured_database" ]] \
    || die 'Legacy DB is not its bundled bootstrap database; supervised recovery is required.'
  local previous_compose=("${COMPOSE[@]}")
  COMPOSE=("${legacy[@]}")
  plan_key_backfill
  COMPOSE=("${previous_compose[@]}")
  [[ ! -L "$ROOT/backups" ]] || die 'The legacy backup directory cannot be a symlink.'
  mkdir -p "$ROOT/backups"; chmod 700 "$ROOT/backups"
  local backup="$ROOT/backups/pre-h1-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
  local db_user
  db_user="$(deployment_value POSTGRES_USER)"; db_user="${db_user:-makerspace}"
  (umask 077; "${legacy[@]}" exec -T db pg_dump --format=custom --no-owner --no-acl \
    -U "$db_user" "$active_name" > "$backup") || die 'Legacy backup failed; no transition was started.'
  [[ -s "$backup" ]] || die 'Empty legacy backup; no transition was started.'
  cp -p "$ROOT/.env" "$backup.env"; chmod 600 "$backup.env"
  # Durable intent precedes all layout changes. It is deliberately never guessed away.
  python3 - "$ROOT/.spaceworks-transition.json" "$current" "$old_identity" <<'PY'
import json, os, sys
with open(sys.argv[1], 'x', encoding='utf-8') as handle:
    os.chmod(sys.argv[1], 0o600)
    json.dump({'schema_version': 1, 'release': sys.argv[2], 'identity': sys.argv[3], 'phase': 'backed-up'}, handle)
    handle.flush(); os.fsync(handle.fileno())
PY
  if [[ "${SPACEWORKS_OPERATION_LOCK_HELD:-0}" != 1 ]]; then
    local old_image_id host_gid
    old_image_id="$(docker inspect --format '{{.Image}}' "$container")" || return
    [[ "$old_image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || die 'Cannot pin the verified legacy image for host lock provisioning.'
    host_gid="$(id -g)"
    docker run --rm --user 0:0 --network none --entrypoint sh \
      -v "$OPS_DIR:/ops" "$old_image_id" -c \
      "set -e; mkdir -p /ops/work; chown 10001:10001 /ops/work; chmod 700 /ops/work; touch /ops/operation.lock; chown 0:0 /ops/operation.lock; chmod 666 /ops/operation.lock; chown 0:$host_gid /ops; chmod 750 /ops"
    exec 8>"$OPS_DIR/operation.lock"
    flock -n 8 || die 'Another host operation acquired the newly provisioned lock.'
    SPACEWORKS_OPERATION_LOCK_HELD=1
  fi
  "${legacy[@]}" stop backend live worker beat
  source "$UPDATE_SCRIPT_DIR/setup-question-input.sh"
  source "$UPDATE_SCRIPT_DIR/setup-write-environment.sh"
  apply_key_backfill
  grep -q '^POSTGRES_APP_PASSWORD=' "$ROOT/.env" || printf '\nPOSTGRES_APP_PASSWORD=%s\n' "$(rand_key 32)" >> "$ROOT/.env"
  grep -q '^SPACEWORKS_SCHEDULER_MODE=' "$ROOT/.env" || printf '\nSPACEWORKS_SCHEDULER_MODE=image\n' >> "$ROOT/.env"
  grep -q '^EVENT_STATION_PIN_PEPPER=' "$ROOT/.env" || printf '\nEVENT_STATION_PIN_PEPPER=%s\n' "$(rand_key 50)" >> "$ROOT/.env"
  install_staged_host_bundle "$(cd "$UPDATE_SCRIPT_DIR/.." && pwd)"
  HOST_CONFIG_IMAGE="$MAKERSPACE_BACKEND_IMAGE:$REQUESTED_VERSION"
  SPACEWORKS_HOST_CONFIG_BUILD=0
  source "$UPDATE_SCRIPT_DIR/setup-host-orchestration.sh"
  prepare_compose_wrapper
  COMPOSE=("$ROOT/scripts/spaceworks-compose.sh" bundled)
  # No old writers are readmitted. New entrypoints provision grants and identity.
  "${COMPOSE[@]}" up -d --remove-orphans
  wait_for_backend || die 'Legacy transition is incomplete; writers remain fenced by the installed H1 boundary.'
  install_producer_capability
  rm -f "$ROOT/.spaceworks-transition.json"
  rm -rf -- "$stage"
  say 'Pre-H1 transition v1 complete; the private backup and original environment are retained.'
}
