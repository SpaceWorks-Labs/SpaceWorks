#!/usr/bin/env bash
# Database steps of scripts/restore.sh. Sourced after COMPOSE, RESTORE_ID, RESTORE_SCRIPT_DIR,
# die() and deployment_value() exist. The bundled path runs inside the `db` container exactly as
# before; SPACEWORKS_DATABASE=external has no `db` container, so the same steps run in a one-off
# backend container against the OWNER login (SPACEWORKS_MAINTENANCE_DATABASE_URL), through
# scripts/installer/external-restore-db.py: version-matched 16/17 client, direct or session
# connection only (a transaction pooler is refused), never the narrow runtime login.

restore_database_is_external() { [[ "$(deployment_value SPACEWORKS_DATABASE)" == external ]]; }

restore_container_path() { printf '/var/lib/spaceworks/ops/work/restore-%s/%s' "$RESTORE_ID" "$1"; }

# env_setting() escapes backslash and single quote; undo it before handing the URL to the container.
external_step() {
  local url mode
  url="$(deployment_value SPACEWORKS_MAINTENANCE_DATABASE_URL | sed 's/\\\(.\)/\1/g')"
  [[ -n "$url" ]] || die 'SPACEWORKS_MAINTENANCE_DATABASE_URL (the outside database owner login) is missing from .env.'
  mode="$(deployment_value DATABASE_MAINTENANCE_CONNECTION_MODE)"
  [[ -n "$mode" ]] || mode="$(deployment_value DATABASE_CONNECTION_MODE)"
  DATABASE_URL="$url" DATABASE_CONNECTION_MODE="${mode:-direct}" "${COMPOSE[@]}" run --rm --no-deps -T \
    -e DATABASE_URL -e DATABASE_CONNECTION_MODE backend --role management python - "$@" \
    < "$RESTORE_SCRIPT_DIR/installer/external-restore-db.py"
}

# The runtime pointer and the owner login must name the same database before anything runs.
prove_external_restore_database() {
  local active bootstrap
  active="$("${COMPOSE[@]}" run --rm --no-deps -T backend --role management python - identity \
    < "$RESTORE_SCRIPT_DIR/installer/external-restore-db.py")" \
    || die 'Cannot prove the active database identity; restore refused.'
  bootstrap="$(external_step identity)" \
    || die 'Cannot prove the outside database identity with the owner login; restore refused.'
  active="${active//$'\r'/}"; bootstrap="${bootstrap//$'\r'/}"
  [[ "$active" =~ ^([A-Za-z_][A-Za-z0-9_$]{0,62})\|[0-9]+\|[0-9a-f-]{36}$ ]] \
    || die 'Invalid active database identity; restore refused.'
  [[ "$active" == "$bootstrap" ]] \
    || die 'The runtime database pointer differs from the owner database; restore refused.'
  RESTORE_DATABASE="${active%%|*}"
}

# An outside database is replaced only on explicit confirmation unless nothing is in it yet.
confirm_external_replace() {
  local accounts typed
  restore_database_is_external || return 0
  accounts="$(external_step has-data | tr -d '\r')" || die 'Cannot read the outside database; restore refused.'
  [[ "$accounts" =~ ^[0-9]+$ ]] || die 'Cannot read the outside database; restore refused.'
  (( accounts > 0 )) || return 0
  [[ "${REPLACE_CONFIRMED:-0}" != 1 ]] || return 0
  [[ -t 0 && -t 1 ]] || die "The outside database $RESTORE_DATABASE already holds data and this restore REPLACES it. A pre-restore dump is taken first. Rerun with --replace to confirm."
  printf 'The outside database %s already holds data and this restore REPLACES it.\nType the database name to continue: ' "$RESTORE_DATABASE" >&2
  IFS= read -r typed || die 'Restore cancelled.'
  [[ "$typed" == "$RESTORE_DATABASE" ]] || die 'Restore cancelled; nothing was changed.'
}

# Prints "oid|uuid" of the named database ($1 empty = the restore database).
restore_db_grant_proof() {
  local database_name="${1:-$RESTORE_DATABASE}"
  if restore_database_is_external; then
    local scratch=()
    [[ "$database_name" == "$RESTORE_DATABASE" ]] || scratch=("$database_name")
    external_step identity ${scratch[@]+"${scratch[@]}"} | tr -d '\r' | cut -d'|' -f2-
    return "${PIPESTATUS[0]}"
  fi
  "${COMPOSE[@]}" exec -T -e "SPACEWORKS_RESTORE_DATABASE=$database_name" db sh -c \
    'psql -X -v ON_ERROR_STOP=1 -At -F "|" -U "$POSTGRES_USER" -d "$SPACEWORKS_RESTORE_DATABASE" -c "SELECT d.oid, i.database_uuid FROM pg_database d CROSS JOIN backup_deploymentdatabaseidentity i WHERE d.datname=current_database() AND i.id=1"'
}

# Mandatory snapshot before any destructive step, written to $PRE_DB.
restore_db_snapshot() {
  if restore_database_is_external; then
    external_step dump "$(restore_container_path pre-restore.dump)"
    return
  fi
  ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T -e "SPACEWORKS_RESTORE_DATABASE=$RESTORE_DATABASE" db sh -c \
    'pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" "$SPACEWORKS_RESTORE_DATABASE"' \
    > "$PRE_DB"
}

# Put the pre-restore snapshot back (rollback after a failed or interrupted restore).
restore_db_rollback() {
  if restore_database_is_external; then
    external_step restore "$(restore_container_path pre-restore.dump)"
    return
  fi
  ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T -e "SPACEWORKS_RESTORE_DATABASE=$RESTORE_DATABASE" db sh -c \
    'pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$SPACEWORKS_RESTORE_DATABASE"' \
    < "$PRE_DB"
}

# The archive's database replaces the live one.
restore_db_replace() {
  if restore_database_is_external; then
    external_step restore "$(restore_container_path bundle/database.dump)"
    return
  fi
  ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T -e "SPACEWORKS_RESTORE_DATABASE=$RESTORE_DATABASE" db sh -c \
    'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$SPACEWORKS_RESTORE_DATABASE" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()" >/dev/null && pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$SPACEWORKS_RESTORE_DATABASE"' \
    < "$BUNDLE/database.dump"
}

# Scratch sibling database for the in-place rollback diff ($1 = its name).
restore_db_scratch_load() {
  local temp_db="$1"
  if restore_database_is_external; then
    external_step create-scratch "$temp_db" \
      && external_step restore-scratch "$temp_db" "$(restore_container_path bundle/database.dump)"
    return
  fi
  ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T -e "SPACEWORKS_RESTORE_DATABASE=$RESTORE_DATABASE" db sh -c \
    'dropdb --if-exists -U "$POSTGRES_USER" '"$temp_db"' && createdb -U "$POSTGRES_USER" '"$temp_db"
  ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T -e "SPACEWORKS_RESTORE_DATABASE=$RESTORE_DATABASE" db sh -c \
    'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d '"$temp_db" \
    < "$BUNDLE/database.dump"
}

restore_db_scratch_drop() {
  local temp_db="$1"
  if restore_database_is_external; then
    external_step drop-scratch "$temp_db" >/dev/null 2>&1 || true
    return
  fi
  ${COMPOSE[@]+"${COMPOSE[@]}"} exec -T -e "SPACEWORKS_RESTORE_DATABASE=$RESTORE_DATABASE" db sh -c \
    'dropdb --if-exists -U "$POSTGRES_USER" '"$temp_db" >/dev/null 2>&1 || true
}
