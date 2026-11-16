#!/usr/bin/env bash
# Setup checkpoints and compatibility keys; operation.lock must be held by caller.
checkpoint_install() {
  [[ ! -f "$ROOT/.spaceworks-version" ]] || return 0
  [[ -f "$ROOT/.spaceworks-install.json" ]] || return 0
  python3 "$ROOT/scripts/installer/state.py" phase --root "$ROOT" \
    --repository "$SPACEWORKS_REPOSITORY" --release "$MAKERSPACE_IMAGE_TAG" --phase "$1"
}

ensure_station_pepper() {
  local pepper
  if [[ "$(uname -s)" == Linux && "${SPACEWORKS_OPERATION_LOCK_HELD:-0}" != 1 ]]; then
    die 'Station continuity backfill requires the held host operation lock.'
  fi
  if grep -q '^EVENT_STATION_PIN_PEPPER=' "$ROOT/.env"; then
    pepper="$(deployment_value EVENT_STATION_PIN_PEPPER)"
    [[ ${#pepper} -ge 32 && "$pepper" != *$'\n'* ]] || die 'Existing station pepper is invalid; recover its original value rather than rotating it.'
  else
    printf '\nEVENT_STATION_PIN_PEPPER=%s\n' "$(rand_key 50)" >> "$ROOT/.env"
    checkpoint_install environment
    [[ "${1:-refresh}" == no-refresh ]] || refresh_compose_config
  fi
}

save_bootstrap_credential() {
  [[ "${GEN_PASS:-0}" == 1 ]] || return 0
  SETUP_BOOTSTRAP_PASSWORD="$ADMINPASS" SETUP_BOOTSTRAP_USER="$ADMINUSER" \
    python3 "$ROOT/scripts/installer/credential.py" "$ROOT/.spaceworks-bootstrap-credential.json"
}
