#!/usr/bin/env bash
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
  local frontend storage tunnel_port
  frontend="$(deployment_value SPACEWORKS_RUN_FRONTEND)"
  storage="$(deployment_value SPACEWORKS_STORAGE)"
  tunnel_port="$(deployment_value CONTROL_PLANE_TUNNEL_PORT)"
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
  control_plane_settings_valid "$layer" || return 64
  if [[ -n "$tunnel_port" && "$layer" == *tls ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.control-tunnel.yml")
    DEPLOYMENT_SUFFIX+='-control-tunnel'
  fi
}

# Caddy imports control-plane-<value>.caddy and import paths are globs, so `*` would load both
# files: only the exact enum may reach Compose. A tunnel port that shadows a published edge or
# storage port would take that listener down when Caddy is recreated.
control_plane_settings_valid() {
  local layer="$1" proxy port reserved
  proxy="$(deployment_value CONTROL_PLANE_PROXY)"
  [[ -z "$proxy" || "$proxy" == true || "$proxy" == false ]] || { echo 'CONTROL_PLANE_PROXY must be true or false.' >&2; return 64; }
  port="$(deployment_value CONTROL_PLANE_TUNNEL_PORT)"
  [[ -n "$port" && "$layer" == *tls ]] || return 0
  if [[ ! "$port" =~ ^[1-9][0-9]{0,4}$ ]] || (( port > 65535 )); then
    echo 'CONTROL_PLANE_TUNNEL_PORT must be a port from 1 to 65535 without leading zeros.' >&2
    return 64
  fi
  for reserved in "$(deployment_value TLS_HTTP_PORT)" "$(deployment_value TLS_HTTPS_PORT)" \
    "$(deployment_value MINIO_API_PORT)" "$(deployment_value MINIO_CONSOLE_PORT)" 80 443 9000 9001; do
    [[ "$port" != "$reserved" ]] || { echo "CONTROL_PLANE_TUNNEL_PORT $port is already a published HTTP, HTTPS or storage port." >&2; return 64; }
  done
}

require_tunnel_engine() {
  # The installer passes the version it read as its own Docker identity (root or docker group).
  local version="${1-}" major
  [[ $# -gt 0 ]] || version="$(docker version --format '{{.Server.Version}}' 2>/dev/null)" || version=''
  major="${version%%.*}"
  if [[ ! "$major" =~ ^[0-9]+$ ]] || (( 10#$major < 28 )); then
    echo 'The control-plane SSH tunnel needs Docker Engine 28 or newer (older engines expose 127.0.0.1-published ports to neighbouring hosts). Upgrade Docker or clear CONTROL_PLANE_TUNNEL_PORT.' >&2
    return 64
  fi
}

# Service sets follow the saved topology, including on updates and recovery.
deployment_services() {
  local layer="${SPACEWORKS_COMPOSE_LAYER:-}" frontend
  if [[ -z "$layer" && -f "$ROOT/.spaceworks-layer" ]]; then
    layer="$(tr -d '[:space:]' < "$ROOT/.spaceworks-layer")"
  fi
  APP_SERVICE=backend
  WORKER_SERVICES=(worker beat live)
  IMAGE_SERVICES=(orchestration-init migrate orchestration-ready backend live worker beat)
  ROLLBACK_SERVICES=(backend live worker beat)
  RUN_ONCE_SERVICES=(orchestration-init migrate orchestration-ready)
  if [[ "$layer" == single ]]; then
    APP_SERVICE=app
    WORKER_SERVICES=()
    IMAGE_SERVICES=(orchestration-init migrate orchestration-ready app)
    ROLLBACK_SERVICES=(app)
  elif [[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" == no ]]; then
    IMAGE_SERVICES+=(api-edge)
    ROLLBACK_SERVICES+=(api-edge)
  else
    IMAGE_SERVICES+=(frontend)
    ROLLBACK_SERVICES+=(frontend)
  fi
  [[ "$(deployment_value SPACEWORKS_STORAGE)" == external ]] || RUN_ONCE_SERVICES+=(createbuckets)
}
