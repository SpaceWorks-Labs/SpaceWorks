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
  require_capacity "$((8 * 1024 * 1024 + (bytes * 3 + 1023) / 1024))" \
    "$ROOT/backups" "$OPS_DIR/work" "$docker_root"
}
