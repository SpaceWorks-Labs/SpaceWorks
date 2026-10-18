#!/usr/bin/env bash
# Resolve non-secret selectors from committed dotenv, never execute dotenv as shell.
installer_env_value() {
  local key="$1" value
  value="$(sed -n "s/^$key=//p" "${STATIC_ENV:-$ROOT/.env}" | tr -d '\r')" || return
  [[ "$value" != *$'\n'* ]] || { echo "Duplicate host selector: $key" >&2; return 64; }
  value="${value#\'}"; value="${value%\'}"
  value="${value#\"}"; value="${value%\"}"
  printf '%s' "$value"
}

validate_host_path() {
  local path="$1" part cursor='' mode owner
  [[ "$path" == /* && "$path" != / && "$path" != */ && "$path" != *//* \
     && "$path" != *$'\n'* && "$path" != *$'\r'* && "$path" != *:* \
     && "$path" != *"'"* && "$path" != *\\* ]] || {
    echo 'Host state paths must be canonical absolute directories.' >&2; return 64;
  }
  local parts=(); IFS=/ read -ra parts <<< "$path"
  for part in "${parts[@]}"; do
    [[ -n "$part" ]] || continue
    [[ "$part" != . && "$part" != .. ]] || return 64
    cursor+="/$part"
    [[ ! -L "$cursor" ]] || { echo 'Host state path contains a symlink.' >&2; return 64; }
    [[ ! -e "$cursor" || -d "$cursor" ]] || return 64
  done
  if [[ -d "$path" && "$(uname -s)" == Linux ]]; then
    owner="$(stat -c %u "$path")"; mode="$(stat -c %a "$path")"
    [[ "$owner" == 0 || "$owner" == "$(id -u)" ]] && (( (8#$mode & 0022) == 0 )) || {
      echo 'Host state directory has an unsafe owner or write permissions.' >&2; return 64;
    }
  fi
}

resolve_host_paths() {
  local key saved ambient fallback
  for key in SPACEWORKS_OPS_HOST_DIR SPACEWORKS_HOST_STATE_DIR; do
    saved="$(installer_env_value "$key")" || return
    ambient="${!key:-}"
    if [[ -n "$saved" && -n "$ambient" && "$saved" != "$ambient" ]]; then
      echo "Ambient $key disagrees with the saved installation; refusing." >&2; return 64
    fi
    fallback=/var/lib/spaceworks/ops
    [[ "$key" != SPACEWORKS_HOST_STATE_DIR ]] || fallback=/var/lib/spaceworks/host
    printf -v "$key" '%s' "${saved:-${ambient:-$fallback}}"
    validate_host_path "${!key}" || return
    export "$key"
  done
  [[ "$SPACEWORKS_HOST_STATE_DIR/" != "$SPACEWORKS_OPS_HOST_DIR/"* \
     && "$SPACEWORKS_OPS_HOST_DIR/" != "$SPACEWORKS_HOST_STATE_DIR/"* ]] || {
    echo 'Host authority and operation directories must be separate.' >&2; return 64;
  }
  OPS_DIR="$SPACEWORKS_OPS_HOST_DIR"
  OPS_HOST_DIR="$OPS_DIR"
  HOST_STATE_DIR="$SPACEWORKS_HOST_STATE_DIR"
}
