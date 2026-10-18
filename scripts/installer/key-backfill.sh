#!/usr/bin/env bash
# Plan with the old admitted backend before files/env change. Apply under the
# operation lock and the caller's exact configuration snapshot/rollback boundary.
plan_key_backfill() {
  SEED_PII_MASTER=0; SEED_PII_SEARCH=0
  local master search previous broker proof
  master="$(deployment_value PII_MASTER_KEY)"
  search="$(deployment_value PII_SEARCH_HASH_KEY)"
  previous="$(deployment_value PII_MASTER_KEY_PREVIOUS)"
  PII_MASTER_KEY="$master" PII_MASTER_KEY_PREVIOUS="$previous" PII_SEARCH_HASH_KEY="$search" \
    python3 "$(dirname "${BASH_SOURCE[0]}")/key-format.py" || die 'Existing encryption material failed validation.'
  broker="$(deployment_value PII_KEY_BROKER)"; broker="${broker:-local}"
  [[ -n "$master" || "$broker" != local ]] || SEED_PII_MASTER=1
  [[ -n "$search" ]] || SEED_PII_SEARCH=1
  [[ -z "$master" || "$SEED_PII_SEARCH" == 1 ]] || return 0
  proof="$("${COMPOSE[@]}" exec -T backend python -c \
    "$(cat "$(dirname "${BASH_SOURCE[0]}")/key-backfill-probe.py")")" || \
    die 'Cannot prove missing encryption material is unused. Start the previous admitted backend or recover its original keys.'
  proof="${proof//$'\r'/}"
  [[ "$proof" =~ ^[01]\|[01]$ ]] || die 'Invalid encryption continuity proof.'
  if [[ -z "$master" && "${proof%%|*}" != 1 ]]; then
    die 'Local encrypted keys already exist; restore PII_MASTER_KEY from recovery custody instead of generating one.'
  fi
  if [[ "$SEED_PII_SEARCH" == 1 && "${proof##*|}" != 1 ]]; then
    die 'Search-key generations already exist; recover PII_SEARCH_HASH_KEY instead of replacing search identity.'
  fi
}

apply_key_backfill() {
  local temporary key
  if [[ "${SEED_PII_MASTER:-0}" == 1 || "${SEED_PII_SEARCH:-0}" == 1 ]]; then
    # Empty legacy declarations are removed only after the read-only unused proof.
    temporary="$(mktemp "$ROOT/.key-backfill.XXXXXX")" || return
    cp -p "$ROOT/.env" "$temporary" || return
    for key in PII_MASTER_KEY PII_SEARCH_HASH_KEY; do
      if [[ "$key" == PII_MASTER_KEY && "${SEED_PII_MASTER:-0}" == 1 \
         || "$key" == PII_SEARCH_HASH_KEY && "${SEED_PII_SEARCH:-0}" == 1 ]]; then
        local filtered
        filtered="$(mktemp "$ROOT/.key-backfill.XXXXXX")" || return
        sed "/^$key=/d" "$temporary" > "$filtered" || return
        mv -f "$filtered" "$temporary" || return
      fi
    done
    chmod 600 "$temporary"
    [[ "${SEED_PII_MASTER:-0}" != 1 ]] || env_setting PII_MASTER_KEY "$(fernet_key)" "$temporary" || return
    [[ "${SEED_PII_SEARCH:-0}" != 1 ]] || env_setting PII_SEARCH_HASH_KEY "$(fernet_key)" "$temporary" || return
    mv -f "$temporary" "$ROOT/.env" || return
  fi
}
