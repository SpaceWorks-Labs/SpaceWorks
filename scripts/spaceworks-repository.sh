#!/usr/bin/env bash
# Read only named configuration values; never execute the private .env as shell code.
repository_env_value() {
  local key="$1" value="" file="${SPACEWORKS_STATIC_ENV_FILE:-$ROOT/.env}"
  if [[ -f "$file" ]]; then
    value="$(sed -n "s/^${key}=//p" "$file" | tail -n 1 | tr -d '\r')"
    if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then value="${value:1:${#value}-2}"; fi
  fi
  printf '%s' "$value"
}

# Owner decision #107: the GitHub org SpaceWorks-HQ was renamed SpaceWorks-Labs and its
# images moved to ghcr.io/spaceworks-labs. Print the renamed value for an old official
# name, or nothing. Forks and every other owner are left untouched.
renamed_release_value() {
  local key="$1" value="$2" lower
  lower="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  case "$key" in
    SPACEWORKS_REPOSITORY)
      [[ "$lower" == spaceworks-hq/* ]] && printf 'SpaceWorks-Labs/%s' "${value#*/}" ;;
    MAKERSPACE_BACKEND_IMAGE|MAKERSPACE_FRONTEND_IMAGE)
      [[ "$lower" == ghcr.io/spaceworks-hq/* ]] && printf 'ghcr.io/spaceworks-labs/%s' "${value#ghcr.io/*/}" ;;
  esac
  return 0
}

# Rewrite saved and exported release coordinates that still name the old org, persist the
# saved ones to the env file (content replaced in place so owner and mode are kept), and
# log each change.
migrate_renamed_release_owner() {
  local file="${SPACEWORKS_STATIC_ENV_FILE:-$ROOT/.env}" key saved renamed current tmp
  for key in SPACEWORKS_REPOSITORY MAKERSPACE_BACKEND_IMAGE MAKERSPACE_FRONTEND_IMAGE; do
    saved="$(repository_env_value "$key")"
    renamed="$(renamed_release_value "$key" "$saved")"
    if [[ -n "$renamed" && -f "$file" && -w "$file" ]]; then
      tmp="$(mktemp "${file}.rename.XXXXXX")" || return 1
      awk -v key="$key" -v value="$renamed"         'index($0, key "=") == 1 { print key "=" value; next } { print }' "$file" > "$tmp"         && cat "$tmp" > "$file"
      rm -f "$tmp"
      printf 'NOTICE: %s changed from %s to %s in %s (GitHub org SpaceWorks-HQ is now SpaceWorks-Labs).
'         "$key" "$saved" "$renamed" "$file" >&2
    fi
    current="${!key:-}"
    renamed="$(renamed_release_value "$key" "$current")"
    if [[ -n "$renamed" ]]; then
      printf 'NOTICE: %s %s is now %s (GitHub org SpaceWorks-HQ is now SpaceWorks-Labs).
'         "$key" "$current" "$renamed" >&2
      printf -v "$key" '%s' "$renamed"
    fi
  done
}

configure_release_repository() {
  local owner key value
  migrate_renamed_release_owner || return 1
  SPACEWORKS_REPOSITORY="${SPACEWORKS_REPOSITORY:-$(repository_env_value SPACEWORKS_REPOSITORY)}"
  SPACEWORKS_REPOSITORY="${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}"
  [[ "$SPACEWORKS_REPOSITORY" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}$ ]] \
    && [[ "$SPACEWORKS_REPOSITORY" != */. && "$SPACEWORKS_REPOSITORY" != */.. ]] || {
    printf 'ERROR: SPACEWORKS_REPOSITORY must be a GitHub owner/repo name.\n' >&2
    return 1
  }
  owner="$(printf '%s' "${SPACEWORKS_REPOSITORY%%/*}" | tr '[:upper:]' '[:lower:]')"
  for key in MAKERSPACE_BACKEND_IMAGE MAKERSPACE_FRONTEND_IMAGE; do
    value="${!key:-$(repository_env_value "$key")}"
    if [[ -z "$value" ]]; then
      case "$key" in
        MAKERSPACE_BACKEND_IMAGE) value="ghcr.io/$owner/spaceworks-backend" ;;
        MAKERSPACE_FRONTEND_IMAGE) value="ghcr.io/$owner/spaceworks-frontend" ;;
      esac
    fi
    export "$key=$value"
  done
  export SPACEWORKS_REPOSITORY
}
