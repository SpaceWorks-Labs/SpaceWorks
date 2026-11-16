#!/usr/bin/env bash
# Use the updater's portable exclusion, then the shared host lock when it exists.
acquire_setup_lock() {
  SETUP_LOCK_DIR="$ROOT/.spaceworks-update.lock"
  local owner=''
  if ! mkdir -m 700 "$SETUP_LOCK_DIR" 2>/dev/null; then
    [[ -d "$SETUP_LOCK_DIR" && ! -L "$SETUP_LOCK_DIR" ]] || return 1
    read -r owner _ < "$SETUP_LOCK_DIR/owner" || return 1
    [[ "$owner" =~ ^[0-9]+$ ]] || return 1
    ! kill -0 "$owner" 2>/dev/null || return 1
    rm -f -- "$SETUP_LOCK_DIR/owner" || return
    rmdir "$SETUP_LOCK_DIR" || return
    mkdir -m 700 "$SETUP_LOCK_DIR" || return
  fi
  printf '%s %s\n' "$$" "$(date +%s)" > "$SETUP_LOCK_DIR/owner"
}

lock_setup_operation() {
  [[ "${SPACEWORKS_OPERATION_LOCK_HELD:-0}" != 1 ]] || return 0
  if command -v flock >/dev/null 2>&1; then
    [[ ! -L "$OPS_HOST_DIR/operation.lock" ]] || return 1
    exec 9>"$OPS_HOST_DIR/operation.lock"
    flock -n 9 || return
    SPACEWORKS_OPERATION_LOCK_HELD=1
  elif [[ "$(uname -s)" == Linux ]]; then
    echo 'Linux setup requires flock before host-state changes.' >&2; return 64
  fi
}

release_setup_lock() {
  local owner=''
  if [[ -f "${SETUP_LOCK_DIR:-}/owner" ]]; then
    read -r owner _ < "$SETUP_LOCK_DIR/owner" || true
    if [[ "$owner" == "$$" ]]; then
      rm -f -- "$SETUP_LOCK_DIR/owner"
      rmdir -- "$SETUP_LOCK_DIR"
    fi
  fi
}
