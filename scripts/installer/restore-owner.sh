#!/usr/bin/env bash
# Destructive restore is a root operation even for an operator-owned install.
# The wrapper independently trusts only that install owner's private static env.
require_restore_root() {
  local entrypoint="$1"; shift
  [[ "$(uname -s)" == Linux ]] || {
    echo 'Destructive restore/import requires Linux or WSL2.' >&2; exit 64;
  }
  if [[ "$(id -u)" != 0 ]]; then
    command -v sudo >/dev/null 2>&1 || { echo 'Run this restore/import with sudo as root.' >&2; exit 64; }
    local key forwarded=("SPACEWORKS_UPDATE_INSTALL_DIR=$ROOT")
    for key in SPACEWORKS_OPS_HOST_DIR SPACEWORKS_HOST_STATE_DIR SPACEWORKS_STATIC_ENV_FILE \
      SPACEWORKS_COMPOSE_LAYER SPACEWORKS_COMPOSE_BUILD_LAYER SPACEWORKS_REPOSITORY \
      MAKERSPACE_IMAGE_TAG MAKERSPACE_BACKEND_IMAGE BACKUP_AGE_IDENTITY_FILE; do
      [[ -z "${!key:-}" ]] || forwarded+=("$key=${!key}")
    done
    echo 'Continuing privileged restore/import as root using sudo.' >&2
    exec sudo env "${forwarded[@]}" bash "$entrypoint" "$@"
  fi
  (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4) )) || exit 64
  python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1 || {
    echo 'Privileged restore/import requires host Python 3.10+; prepare it with the current installer first.' >&2; exit 64;
  }
}
