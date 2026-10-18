#!/usr/bin/env bash
# Called under operation.lock, before any restore-control or destructive effect.
prove_restore_database() {
  local active bootstrap
  active="$("${COMPOSE[@]}" run --rm --no-deps -T backend --role management python -c \
    "$(cat "$RESTORE_SCRIPT_DIR/restore-database-identity.py")")" \
    || die 'Cannot prove the active database identity; restore refused.'
  bootstrap="$("${COMPOSE[@]}" exec -T db sh -c \
    'psql -X -v ON_ERROR_STOP=1 -At -F "|" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database(), d.oid, i.database_uuid FROM pg_database d CROSS JOIN backup_deploymentdatabaseidentity i WHERE d.datname=current_database() AND i.id=1"')" \
    || die 'Cannot prove the bootstrap database identity; restore refused.'
  active="${active//$'\r'/}"; bootstrap="${bootstrap//$'\r'/}"
  [[ "$active" =~ ^([A-Za-z_][A-Za-z0-9_$]{0,62})\|[0-9]+\|[0-9a-f-]{36}$ ]] \
    || die 'Invalid active database identity; restore refused.'
  [[ "$active" == "$bootstrap" ]] \
    || die 'Active database pointer differs from the bootstrap database; legacy restore refused. Use the supported cutover recovery coordinator.'
  RESTORE_DATABASE="${active%%|*}"
  # Exact database is then passed explicitly to dump, restore and grant commands.
}
