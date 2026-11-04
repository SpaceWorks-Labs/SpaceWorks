#!/usr/bin/env bash
# Apply host proxy settings while keeping the running release and database pointer.
set -euo pipefail

control_plane_probe_target() {
  local layer="${1:-${LAYER:-none}}" domain port
  domain="$(deployment_value PUBLIC_DOMAIN)"
  if [[ "$layer" == tls ]]; then
    port="$(deployment_value TLS_HTTPS_PORT)"; port="${port:-443}"
    printf '%s\n' "https://$domain:$port" --resolve "$domain:$port:127.0.0.1" -k
    return 0
  fi
  # API-only installs publish the api-edge listener (API_PORT), not the website's.
  if [[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" == no ]]; then
    port="$(deployment_value API_PORT)"
  else
    port="$(deployment_value HTTP_PORT)"
  fi
  if [[ "$layer" == none && "$(deployment_value ENABLE_HTTPS)" == true ]]; then
    printf '%s\n' "http://127.0.0.1:${port:-80}" -H "Host: $domain" -H 'X-Forwarded-Proto: https'
  else
    printf '%s\n' "http://127.0.0.1:${port:-80}" -H 'Host: 127.0.0.1'
  fi
}

probe() {
  local url="$1" expected="$2" attempt code; shift 2
  for attempt in {1..6}; do
    code="$(curl --silent --show-error --max-time 10 -o "$PROBE_BODY" -w '%{http_code}' "$@" "$url")" || code=failed
    case "$expected:$code" in
      ready:200|missing:404) return 0 ;;
      on:200) if grep -q csrfmiddlewaretoken "$PROBE_BODY"; then return 0; fi ;;
      on:403) if [[ -n "$CONTROL_PLANE_ALLOW_CIDRS" ]]; then say 'allowlist active'; return 0; fi ;;
      off:200) if ! grep -q csrfmiddlewaretoken "$PROBE_BODY"; then return 0; fi ;;
      tunnel:200) if grep -q csrfmiddlewaretoken "$PROBE_BODY"; then return 0; fi ;;
    esac
    [[ "$attempt" == 6 ]] || sleep 5
  done
  die "Probe failed: $url (HTTP $code; expected $expected)."
}

# Keep the URL/header builder available to callers without applying configuration.
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0
APPLY_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SPACEWORKS_UPDATE_INSTALL_DIR:-$(cd "$APPLY_SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"
export SPACEWORKS_UPDATE_INSTALL_DIR="$ROOT"
STATIC_ENV="$ROOT/.env"
export SPACEWORKS_STATIC_ENV_FILE="$STATIC_ENV"
source "$APPLY_SCRIPT_DIR/install-owner.sh"
require_install_owner "$APPLY_SCRIPT_DIR/apply-settings.sh" "$@"
say() { printf '[Space Works settings] %s\n' "$*"; }
die() { printf '[Space Works settings] ERROR: %s\n' "$*" >&2; exit 1; }
refuse() { printf '[Space Works settings] ERROR: %s\n' "$*" >&2; exit 64; }
source "$APPLY_SCRIPT_DIR/../frontend/docker/control-plane-allowlist.sh"
CP_MODE=''; NEW_CIDRS=''; NEW_PORT=''; CIDRS_GIVEN=0; PORT_GIVEN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --control-plane|--allow-cidrs|--tunnel-port)
      [[ $# -ge 2 ]] || refuse "Missing value for $1."
      case "$1" in
        --control-plane) CP_MODE="$2"; [[ "$CP_MODE" == on || "$CP_MODE" == off ]] || refuse '--control-plane must be on or off.' ;;
        --allow-cidrs) NEW_CIDRS="$2"; CIDRS_GIVEN=1 ;;
        --tunnel-port) NEW_PORT="$2"; PORT_GIVEN=1 ;;
      esac
      shift 2 ;;
    *) refuse "Unknown argument: $1" ;;
  esac
done
[[ -n "$CP_MODE" || ( "$CIDRS_GIVEN" == 0 && "$PORT_GIVEN" == 0 ) ]] || refuse '--allow-cidrs and --tunnel-port require --control-plane.'
[[ "$CP_MODE" != off || "$CIDRS_GIVEN" == 0 ]] || refuse '--allow-cidrs cannot be used with --control-plane off.'
[[ -z "$NEW_CIDRS" ]] || cp_valid_cidr_list "$NEW_CIDRS" || refuse 'Invalid --allow-cidrs.'
[[ -z "$NEW_PORT" ]] || cp_valid_port "$NEW_PORT" || refuse 'Invalid --tunnel-port.'
command -v flock >/dev/null 2>&1 || refuse 'Host flock is required; run this from Linux or WSL2.'
source "$APPLY_SCRIPT_DIR/compose-deployment.sh"
source "$APPLY_SCRIPT_DIR/spaceworks-repository.sh"
OPS_DIR="${SPACEWORKS_OPS_HOST_DIR:-$(repository_env_value SPACEWORKS_OPS_HOST_DIR)}"
OPS_DIR="${OPS_DIR:-/var/lib/spaceworks/ops}"
export SPACEWORKS_OPS_HOST_DIR="$OPS_DIR"
LOCK_DIR="$ROOT/.spaceworks-update.lock"
source "$APPLY_SCRIPT_DIR/update-lock.sh"
APPLY_STARTED=0; ENV_REWRITTEN=0; PROBE_BODY=''; ENV_TEMP=''
rollback_control_plane() {
  ROLLBACK_STEP='restoring .env'
  cp -p -- "$ROOT/.env.before-control-plane" "$ROOT/.env" || return
  if [[ "$APPLY_STARTED" == 0 ]]; then
    printf '%s\n' 'The previous .env was restored; nothing else changed.'
    return 0
  fi
  ROLLBACK_STEP='refreshing topology records'
  if ! declare -F refresh_compose_config >/dev/null; then source "$APPLY_SCRIPT_DIR/setup-host-orchestration.sh" || return; fi
  refresh_compose_config || return
  ROLLBACK_STEP='restarting services'
  "$ROOT/scripts/spaceworks-compose.sh" bundled up -d --remove-orphans --pull never --wait --wait-timeout 300 || return
  printf '%s\n' 'Rolled back to the previous control-plane settings.'
}
cleanup() {
  local status=$?
  trap - EXIT
  set +e
  [[ -z "$PROBE_BODY" ]] || rm -f -- "$PROBE_BODY"
  [[ -z "$ENV_TEMP" ]] || rm -f -- "$ENV_TEMP"
  if [[ "$status" != 0 && "$ENV_REWRITTEN" == 1 ]]; then
    if ! rollback_control_plane >&2; then
      printf 'Rollback incomplete (%s failed).\n' "$ROLLBACK_STEP" >&2
      printf '%s\n' 'The previous settings are kept at .env.before-control-plane.' \
        'Copy it over .env if it is not already: cp -p .env.before-control-plane .env' \
        'Then run: bash scripts/apply-settings.sh' \
        'If that refuses because the app service is not running, first run: scripts/spaceworks-compose.sh bundled up -d --pull never' >&2
    fi
  elif [[ "$status" != 0 && "$APPLY_STARTED" == 1 ]]; then
    printf '%s\n' 'Applying failed. Restore the .env you had before editing (the docs suggest keeping `.env.before-control-plane`), then rerun bash scripts/apply-settings.sh. The database was not touched.' >&2
  fi
  release_update_lock
  exit "$status"
}
trap cleanup EXIT
acquire_update_lock
if [[ -n "$CP_MODE" ]]; then
  cp -p -- "$ROOT/.env" "$ROOT/.env.before-control-plane"
  ENV_TEMP="$(umask 077; mktemp "$ROOT/.env.control-plane.XXXXXX")"
  sed '/^[[:space:]]*\(export[[:space:]]\+\)\?CONTROL_PLANE_\(PROXY\|ALLOW_CIDRS\|TUNNEL_PORT\)=/d' "$ROOT/.env" > "$ENV_TEMP"
  # A hand-edited .env may lack its final newline; appending would join two settings.
  [[ ! -s "$ENV_TEMP" || -z "$(tail -c 1 "$ENV_TEMP")" ]] || printf '\n' >> "$ENV_TEMP"
  proxy=false; [[ "$CP_MODE" != on ]] || proxy=true
  printf "CONTROL_PLANE_PROXY='%s'\n" "$proxy" >> "$ENV_TEMP"
  for key in ALLOW_CIDRS TUNNEL_PORT; do
    if [[ "$key" == ALLOW_CIDRS ]]; then value="$NEW_CIDRS"; else value="$NEW_PORT"; fi
    [[ -n "$value" ]] || continue
    value="${value//\\/\\\\}"; value="${value//\'/\\\'}"
    printf "CONTROL_PLANE_%s='%s'\n" "$key" "$value" >> "$ENV_TEMP"
  done
  chmod 600 "$ENV_TEMP"
  mv -f -- "$ENV_TEMP" "$ROOT/.env"
  ENV_REWRITTEN=1
fi
LAYER=none
[[ ! -f "$ROOT/.spaceworks-layer" ]] || LAYER="$(tr -d '[:space:]' < "$ROOT/.spaceworks-layer")"
case "$LAYER" in none|tls) ;; *) refuse 'Settings apply supports bundled release layers none and tls; build layers and saas are not supported.' ;; esac
export SPACEWORKS_COMPOSE_LAYER="$LAYER"
unset SPACEWORKS_COMPOSE_BUILD_LAYER
CONTROL_PLANE_PROXY="$(deployment_value CONTROL_PLANE_PROXY)"
CONTROL_PLANE_ALLOW_CIDRS="$(deployment_value CONTROL_PLANE_ALLOW_CIDRS)"
CONTROL_PLANE_TUNNEL_PORT="$(deployment_value CONTROL_PLANE_TUNNEL_PORT)"
export CONTROL_PLANE_PROXY CONTROL_PLANE_ALLOW_CIDRS CONTROL_PLANE_TUNNEL_PORT
case "$CONTROL_PLANE_PROXY" in true|false|'') ;; *) refuse 'CONTROL_PLANE_PROXY must be true or false.' ;; esac
[[ -z "$CONTROL_PLANE_ALLOW_CIDRS" ]] || cp_valid_cidr_list "$CONTROL_PLANE_ALLOW_CIDRS" || refuse 'Invalid CONTROL_PLANE_ALLOW_CIDRS.'
[[ -z "$CONTROL_PLANE_TUNNEL_PORT" ]] || cp_valid_port "$CONTROL_PLANE_TUNNEL_PORT" || refuse 'Invalid CONTROL_PLANE_TUNNEL_PORT.'
# refresh_compose_config records the TLS topologies on every install, so check them before any
# record is rewritten: a refusal halfway through would leave records out of step with .env.
control_plane_settings_valid tls || exit 64
frontend="$(deployment_value SPACEWORKS_RUN_FRONTEND)"
[[ "$CONTROL_PLANE_PROXY" != true || "$frontend" != no || "$LAYER" == tls ]] || refuse 'API-only control-plane access needs the tls layer; api-edge has no control-plane route.'
if [[ "$LAYER" == tls && -n "$CONTROL_PLANE_TUNNEL_PORT" ]]; then require_tunnel_engine || exit 64; fi
command -v curl >/dev/null 2>&1 || refuse 'curl is required to verify the applied settings.'
deployment_services
running_container() {
  local containers
  local filters=(--filter "label=com.docker.compose.project.working_dir=$ROOT"
    --filter "label=com.docker.compose.service=$1")
  [[ -z "$PROJECT" ]] || filters+=(--filter "label=com.docker.compose.project=$PROJECT")
  containers="$(docker ps "${filters[@]}" --format '{{.ID}}')"
  [[ "$containers" != *$'\n'* ]] || refuse "Multiple running containers found for $1."
  printf '%s' "$containers"
}
PROJECT=''
container="$(running_container "$APP_SERVICE")"
[[ -n "$container" ]] || refuse "The $APP_SERVICE service must be running."
PROJECT="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$container")"
[[ -n "$PROJECT" ]] || refuse 'The running application has no Compose project label.'
export COMPOSE_PROJECT_NAME="$PROJECT"
configure_release_repository
declare -A references identities families
tag=''
for service in "${IMAGE_SERVICES[@]}"; do
  container="$(running_container "$service")"
  [[ -n "$container" ]] || continue
  read -r reference identity <<< "$(docker inspect --format '{{.Config.Image}} {{.Image}}' "$container")"
  references[$service]="$reference"; identities[$service]="$identity"
  [[ "$service" != api-edge ]] || continue
  last="${reference##*/}"
  [[ "$reference" != *@* && "$last" == *:* && -n "${last##*:}" ]] || refuse "Service $service needs a tagged image, not a digest reference."
  current_tag="${last##*:}"; family="${reference%:*}"
  [[ -z "$tag" || "$tag" == "$current_tag" ]] || refuse "Service $service has a different release tag."
  tag="$current_tag"
  case "$service" in frontend) key=MAKERSPACE_FRONTEND_IMAGE ;; *) key=MAKERSPACE_BACKEND_IMAGE ;; esac
  [[ -z "${families[$key]:-}" || "${families[$key]}" == "$family" ]] || refuse "Service $service has a different image family."
  families[$key]="$family"; export "$key=$family"
done
export MAKERSPACE_IMAGE_TAG="$tag"
for service in "${!references[@]}"; do
  case "$service" in
    api-edge) constructed=nginx:alpine ;;
    frontend) constructed="$MAKERSPACE_FRONTEND_IMAGE:$tag" ;;
    *) constructed="$MAKERSPACE_BACKEND_IMAGE:$tag" ;;
  esac
  [[ "$constructed" == "${references[$service]}" ]] || refuse "Image reference changed for $service."
  local_id="$(docker image inspect -f '{{.Id}}' "$constructed")" || refuse "Local image missing for $service."
  [[ "$local_id" == "${identities[$service]}" ]] || refuse "Local image tag was repointed for $service."
done
HOST_CONFIG_IMAGE="${identities[backend]:-}"
if [[ -z "$HOST_CONFIG_IMAGE" ]]; then
  HOST_CONFIG_IMAGE="$(docker image inspect -f '{{.Id}}' "$MAKERSPACE_BACKEND_IMAGE:$tag")" || refuse 'The matching backend image must be available locally for host configuration.'
fi
OPS_HOST_DIR="$OPS_DIR"
export HOST_CONFIG_IMAGE
APPLY_STARTED=1
mkdir -p "$ROOT/backups"
env_backup="$ROOT/backups/env-applied-$(date -u +%Y%m%dT%H%M%SZ)-$$"
(umask 077; cp -- "$ROOT/.env" "$env_backup")
chmod 600 "$env_backup"
source "$APPLY_SCRIPT_DIR/setup-host-orchestration.sh"
refresh_compose_config
"$ROOT/scripts/spaceworks-compose.sh" bundled up -d --remove-orphans --pull never --wait --wait-timeout 300
for service in "${!identities[@]}"; do
  container="$(running_container "$service")"
  [[ -n "$container" && "$(docker inspect --format '{{.Image}}' "$container")" == "${identities[$service]}" ]] || die "Running image changed for $service."
done
PROBE_BODY="$(mktemp "$ROOT/backups/.settings-probe.XXXXXX")"
mapfile -t target < <(control_plane_probe_target)
probe "${target[0]}/api/v1/health/readiness/" ready "${target[@]:1}"
expected=off
if [[ "$CONTROL_PLANE_PROXY" == true ]]; then expected=on
elif [[ "$frontend" == no ]]; then expected=missing; fi
probe "${target[0]}/control/login/" "$expected" "${target[@]:1}"
if [[ "$LAYER" == tls && -n "$CONTROL_PLANE_TUNNEL_PORT" ]]; then
  probe "https://localhost:$CONTROL_PLANE_TUNNEL_PORT/control/login/" tunnel -k
fi
if [[ "$CONTROL_PLANE_PROXY" == true ]]; then say "Control plane: $(deployment_value PUBLIC_APP_BASE_URL)/control/"
else say "Control plane: off (see docs/self-hosting.md, 'Reaching the control plane')"; fi
if [[ "$LAYER" == tls && -n "$CONTROL_PLANE_TUNNEL_PORT" ]]; then
  say "SSH tunnel: ssh -L 8443:127.0.0.1:$CONTROL_PLANE_TUNNEL_PORT <you>@<this server>, then https://localhost:8443/control/"
fi
