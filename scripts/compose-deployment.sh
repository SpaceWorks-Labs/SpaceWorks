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
  local frontend storage database redis tunnel_port
  frontend="$(deployment_value SPACEWORKS_RUN_FRONTEND)"
  storage="$(deployment_value SPACEWORKS_STORAGE)"
  database="$(deployment_value SPACEWORKS_DATABASE)"
  redis="$(deployment_value SPACEWORKS_REDIS)"
  tunnel_port="$(deployment_value CONTROL_PLANE_TUNNEL_PORT)"
  [[ -z "$frontend" || "$frontend" == yes || "$frontend" == no ]] || { echo 'SPACEWORKS_RUN_FRONTEND must be yes or no.' >&2; return 64; }
  [[ -z "$storage" || "$storage" == bundled || "$storage" == external ]] || { echo 'SPACEWORKS_STORAGE must be bundled or external.' >&2; return 64; }
  [[ -z "$database" || "$database" == bundled || "$database" == external ]] || { echo 'SPACEWORKS_DATABASE must be bundled or external.' >&2; return 64; }
  [[ -z "$redis" || "$redis" == bundled || "$redis" == external || "$redis" == none ]] || { echo 'SPACEWORKS_REDIS must be bundled, external or none.' >&2; return 64; }
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
  if [[ "$database" == external ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.external-db.yml")
    DEPLOYMENT_SUFFIX+='-external-db'
  fi
  if [[ "$redis" == external ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.external-redis.yml")
    DEPLOYMENT_SUFFIX+='-external-redis'
  fi
  # No Redis at all (cron mode): drops redis and the worker; beat becomes a scheduler loop. Decision 43's
  # HTTP tick stays free-profile only, so this overlay never sets that profile.
  if [[ "$redis" == none ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.no-redis.yml")
    DEPLOYMENT_SUFFIX+='-no-redis'
  fi
  control_plane_settings_valid "$layer" || return 64
  if [[ -n "$tunnel_port" && "$layer" == *tls ]]; then
    COMPOSE_FILES+=("$prefix/docker/compose.control-tunnel.yml")
    DEPLOYMENT_SUFFIX+='-control-tunnel'
  fi
}

control_plane_port_reserved() {
  local port="$1" reserved
  for reserved in "$(deployment_value TLS_HTTP_PORT)" "$(deployment_value TLS_HTTPS_PORT)" \
    "$(deployment_value MINIO_API_PORT)" "$(deployment_value MINIO_CONSOLE_PORT)" 80 443 9000 9001; do
    [[ "$port" != "$reserved" ]] || return 0
  done
  return 1
}

# Caddy imports control-plane-<value>.caddy and import paths are globs, so `*` would load both
# files: only the exact enum may reach Compose. A tunnel port that shadows a published edge or
# storage port would take that listener down when Caddy is recreated.
control_plane_settings_valid() {
  local layer="$1" proxy port
  proxy="$(deployment_value CONTROL_PLANE_PROXY)"
  [[ -z "$proxy" || "$proxy" == true || "$proxy" == false ]] || { echo 'CONTROL_PLANE_PROXY must be true or false.' >&2; return 64; }
  port="$(deployment_value CONTROL_PLANE_TUNNEL_PORT)"
  [[ -n "$port" && "$layer" == *tls ]] || return 0
  if [[ ! "$port" =~ ^[1-9][0-9]{0,4}$ ]] || (( port > 65535 )); then
    echo 'CONTROL_PLANE_TUNNEL_PORT must be a port from 1 to 65535 without leading zeros.' >&2
    return 64
  fi
  if control_plane_port_reserved "$port"; then
    echo "CONTROL_PLANE_TUNNEL_PORT $port is already a published HTTP, HTTPS or storage port." >&2
    return 64
  fi
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
  refuse_single_box_layer "$layer" || return $?
  APP_SERVICE=backend
  WORKER_SERVICES=(worker beat live)
  IMAGE_SERVICES=(orchestration-init migrate orchestration-ready backend live worker beat)
  ROLLBACK_SERVICES=(backend live worker beat)
  RUN_ONCE_SERVICES=(orchestration-init migrate orchestration-ready)
  if [[ "$(deployment_value SPACEWORKS_REDIS)" == none ]]; then
    # Cron mode parks the worker (docker/compose.no-redis.yml); naming it would start it with no broker.
    WORKER_SERVICES=(beat live)
    IMAGE_SERVICES=(orchestration-init migrate orchestration-ready backend live beat)
    ROLLBACK_SERVICES=(backend live beat)
  fi
  if [[ ",$(deployment_value COMPOSE_PROFILES)," == *,clamav,* ]]; then
    IMAGE_SERVICES+=(clamav)
  fi
  if [[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" == no ]]; then
    IMAGE_SERVICES+=(api-edge)
    ROLLBACK_SERVICES+=(api-edge)
  else
    IMAGE_SERVICES+=(frontend)
    ROLLBACK_SERVICES+=(frontend)
  fi
  [[ "$(deployment_value SPACEWORKS_STORAGE)" == external ]] || RUN_ONCE_SERVICES+=(createbuckets)
}
