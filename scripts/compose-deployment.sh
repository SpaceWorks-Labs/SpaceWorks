#!/usr/bin/env bash
refuse_single_box_layer() {
  [[ "$1" == single ]] || return 0
  cat >&2 <<'MESSAGE'
The single-box install shape (one all-in-one container) was removed and its image
is no longer published. Switch this install to standard containers using the
CURRENTLY INSTALLED scripts, then retry:

  bash scripts/spaceworks-compose.sh bundled stop app
  bash scripts/spaceworks-compose.sh bundled rm -f app
  printf 'none\n' > .spaceworks-layer
  bash scripts/spaceworks-compose.sh bundled up -d

Then re-run the update. Data in the database and storage volumes is unchanged.
See docs/update-recovery.md.
MESSAGE
  return 64
}

# Read only non-secret topology selectors; never source dotenv as shell code.
deployment_value() {
  local value
  value="$(sed -n "s/^$1=//p" "${STATIC_ENV:-${SPACEWORKS_STATIC_ENV_FILE:-$ROOT/.env}}" 2>/dev/null | head -n 1)"
  value="${value#\'}"; value="${value%\'}"
  value="${value#\"}"; value="${value%\"}"
  printf '%s' "$value"
}

append_deployment_layers() {
  local layer="$1" prefix="$2"
  local frontend storage
  frontend="$(deployment_value SPACEWORKS_RUN_FRONTEND)"
  storage="$(deployment_value SPACEWORKS_STORAGE)"
  [[ -z "$frontend" || "$frontend" == yes || "$frontend" == no ]] || { echo 'SPACEWORKS_RUN_FRONTEND must be yes or no.' >&2; return 64; }
  [[ -z "$storage" || "$storage" == bundled || "$storage" == external ]] || { echo 'SPACEWORKS_STORAGE must be bundled or external.' >&2; return 64; }
  DEPLOYMENT_SUFFIX=''
  if [[ "$frontend" == no ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.api-only.yml")
    DEPLOYMENT_SUFFIX+='-api-only'
    if [[ "$layer" == *tls || "$layer" == *saas ]]; then
      COMPOSE_FILES+=("$prefix/docker/compose.api-only-edge.yml")
    fi
  fi
  if [[ "$storage" == external ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.external-storage.yml")
    DEPLOYMENT_SUFFIX+='-external-storage'
  fi
}

# Service sets follow the saved topology, including on updates and recovery.
deployment_services() {
  local layer="${SPACEWORKS_COMPOSE_LAYER:-}" frontend
  if [[ -z "$layer" && -f "$ROOT/.spaceworks-layer" ]]; then
    layer="$(tr -d '[:space:]' < "$ROOT/.spaceworks-layer")"
  fi
  refuse_single_box_layer "$layer" || return $?
  APP_SERVICE=backend
  WORKER_SERVICES=(worker beat live)
  IMAGE_SERVICES=(orchestration-init migrate orchestration-ready backend live worker beat)
  ROLLBACK_SERVICES=(backend live worker beat)
  RUN_ONCE_SERVICES=(orchestration-init migrate orchestration-ready)
  if [[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" == no ]]; then
    IMAGE_SERVICES+=(api-edge)
    ROLLBACK_SERVICES+=(api-edge)
  else
    IMAGE_SERVICES+=(frontend)
    ROLLBACK_SERVICES+=(frontend)
  fi
  [[ "$(deployment_value SPACEWORKS_STORAGE)" == external ]] || RUN_ONCE_SERVICES+=(createbuckets)
}
