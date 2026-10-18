#!/usr/bin/env bash
# Conservative admission before copying images, plaintext SQL and rollback files.
require_capacity() {
  local required_kb="$1" path available
  shift
  for path in "$@"; do
    while [[ ! -e "$path" && "$path" != / ]]; do path="$(dirname "$path")"; done
    available="$(df -Pk "$path" | awk 'NR == 2 {print $4}')" || return
    [[ "$available" =~ ^[0-9]+$ ]] && ((available >= required_kb)) || {
      echo 'Insufficient verified free space for images, working copies and rollback; free space or move the configured state directory.' >&2
      return 1
    }
  done
}

require_upgrade_capacity() {
  local database="$1" bytes docker_root
  bytes="$("${COMPOSE[@]}" exec -T -e "SPACEWORKS_BACKUP_DATABASE=$database" db sh -c \
    'psql -X -v ON_ERROR_STOP=1 -At -U "$POSTGRES_USER" -d "$SPACEWORKS_BACKUP_DATABASE" -c "SELECT pg_database_size(current_database())"')" || return
  bytes="${bytes//$'\r'/}"
  [[ "$bytes" =~ ^[0-9]{1,15}$ ]] || return 1
  docker_root="$(docker info --format '{{.DockerRootDir}}')" || return
  [[ "$docker_root" == /* ]] || return 1
  local paths=("$ROOT/backups" "$OPS_DIR/work")
  [[ "$(uname -s)" != Linux ]] || paths+=("$docker_root")
  require_capacity "$((8 * 1024 * 1024 + (bytes * 3 + 1023) / 1024))" "${paths[@]}"
}

# Run under operation.lock before copy/decrypt, then again with the measured tar
# before extraction. Missing inventory is an admission failure, never zero bytes.
require_operation_capacity() {
  local phase="$1" source_file="${2:-}" plain_file="${3:-}" docker_root metrics directory container image docker_free
  directory="${RESTORE_SCRIPT_DIR:-${UPDATE_SCRIPT_DIR:-$ROOT/scripts}}"
  docker_root="$(docker info --format '{{.DockerRootDir}}')" || return
  [[ "$docker_root" == /* ]] || return 1
  container="$("${COMPOSE[@]}" ps -a -q "$APP_SERVICE")" || return
  image="$(docker inspect --format '{{.Image}}' "$container")" || return
  [[ "$image" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  # Docker Desktop's data root is inside its VM. Measure the daemon filesystem,
  # never mistake a similarly named host directory for the Docker disk.
  docker_free="$(docker run --rm --network none --read-only --entrypoint python "$image" -c \
    'import os; s=os.statvfs("/"); print(s.f_bavail*s.f_frsize)')" || return
  docker_free="${docker_free//$'\r'/}"
  [[ "$docker_free" =~ ^[0-9]+$ ]] || return 1
  if [[ "${SPACEWORKS_CAPACITY_LEGACY:-0}" == 1 ]]; then
    metrics="$("${COMPOSE[@]}" exec -T backend python -c \
      "$(cat "$directory/installer/capacity-metrics.py")")" || return
  else
    metrics="$("${COMPOSE[@]}" run --rm --no-deps -T backend --role management python -c \
      "$(cat "$directory/installer/capacity-metrics.py")" "${RESTORE_ID:-}")" || return
  fi
  local args=(--phase "$phase" --root "$ROOT" --work "$OPS_DIR/work"
    --docker-root "$docker_root" --docker-free "$docker_free" --temp "${TMPDIR:-${TEMP:-/var/tmp}}")
  [[ "$(uname -s)" == Linux ]] || args+=(--docker-separate)
  [[ -z "$source_file" ]] || args+=(--source "$source_file")
  [[ -z "$plain_file" ]] || args+=(--plain "$plain_file")
  printf '%s\n' "$metrics" | python3 "$directory/installer/capacity.py" "${args[@]}"
}
