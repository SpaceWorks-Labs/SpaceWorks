#!/usr/bin/env bash
# Updater readiness and active-pointer SQL backup, under the held operation lock.
wait_for_backend() {
  local _
  for _ in $(seq 1 60); do
    if ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T "$APP_SERVICE" python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/readiness/', timeout=3).read()" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

create_update_backup() {
  [[ ! -L "$ROOT/backups" ]] || die 'The backup directory cannot be a symlink.'
  mkdir -p "$ROOT/backups"
  chmod 700 "$ROOT/backups"
  ${COMPOSE[@]+"${COMPOSE[@]}"} up -d --wait db
  backup_name="pre-update-$(date -u +%Y%m%dT%H%M%SZ)-$$.sql.gz"
  say "Creating database backup backups/$backup_name."
  # Restore can switch to a sibling DB; POSTGRES_DB still names the original bootstrap DB.
  backup_database="$("${COMPOSE[@]}" exec -T "$APP_SERVICE" python -c \
    "$(cat "$UPDATE_SCRIPT_DIR/restore-database-identity.py")" --active-name)"
  backup_database="$(printf '%s' "$backup_database" | tr -d '\r\n')"
  [[ "$backup_database" =~ ^[A-Za-z_][A-Za-z0-9_$]{0,62}$ ]] \
    || die "The active database pointer has an invalid database name; update cancelled."
  source "$UPDATE_SCRIPT_DIR/installer/capacity.sh"
  require_upgrade_capacity "$backup_database" || die 'Insufficient verified capacity; update cancelled.'
  # Write the dump first: POSIX sh pipelines otherwise hide a failed pg_dump behind gzip.
  "${COMPOSE[@]}" exec -T -e "SPACEWORKS_BACKUP_DATABASE=$backup_database" db sh -c \
    'set -e; umask 077; raw="/backups/'"$backup_name"'.raw"; trap '\''rm -f "$raw"'\'' EXIT; pg_dump -U "$POSTGRES_USER" "$SPACEWORKS_BACKUP_DATABASE" > "$raw"; test -s "$raw"; gzip -c "$raw" > "/backups/'"$backup_name"'"' \
    || die "Database backup failed; update cancelled."
  "${COMPOSE[@]}" exec -T db test -s "/backups/$backup_name" \
    || die "Database backup was not created; update cancelled."
  if [[ "$(uname -s)" == Linux ]]; then
    "${COMPOSE[@]}" exec -T db chown "$(id -u):$(id -g)" "/backups/$backup_name" \
      || die 'Cannot protect the private pre-update backup for its install owner.'
  fi
}
