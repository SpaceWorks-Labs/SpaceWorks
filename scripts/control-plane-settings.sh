#!/usr/bin/env bash
# Ask about control-plane access on an installed single-server deployment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
export SPACEWORKS_UPDATE_INSTALL_DIR="$ROOT" SPACEWORKS_STATIC_ENV_FILE="$ROOT/.env"
unset STATIC_ENV
source "$SCRIPT_DIR/install-owner.sh"
require_install_owner "$SCRIPT_DIR/control-plane-settings.sh" "$@"
say() { printf '[Space Works control plane] %s\n' "$*"; }
refuse() { printf '[Space Works control plane] ERROR: %s\n' "$*" >&2; exit 64; }
[[ -f .env ]] || refuse 'This directory is not an installation (.env is missing).'
docker info >/dev/null 2>&1 || refuse "Docker is not reachable as $(id -un). Add this user to the docker group (sudo usermod -aG docker $(id -un)), sign out and back in, then rerun."
source "$SCRIPT_DIR/compose-deployment.sh"
source "$SCRIPT_DIR/setup-question-input.sh"
LAYER=none
[[ ! -f .spaceworks-layer ]] || LAYER="$(tr -d '[:space:]' < .spaceworks-layer)"
case "$LAYER" in
  none|tls) ;;
  *) refuse 'Control-plane access can be changed here for single-server installs only; build layers and saas are not supported.' ;;
esac
[[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" != no || "$LAYER" == tls ]] || refuse 'API-only installs reach the control plane only with automatic HTTPS.'
# Read these keys with the same syntax apply-settings.sh rewrites (indented or `export`ed lines too).
control_value() {
  local value
  value="$(sed -n "s/^[[:space:]]*\(export[[:space:]]\+\)\?$1=//p" .env | tail -n 1)"
  value="${value#\'}"; value="${value%\'}"
  value="${value#\"}"; value="${value%\"}"
  printf '%s' "$value"
}
CONTROL_PLANE_PROXY="$(control_value CONTROL_PLANE_PROXY)"
CONTROL_PLANE_PROXY="${CONTROL_PLANE_PROXY:-false}"
CONTROL_PLANE_ALLOW_CIDRS="$(control_value CONTROL_PLANE_ALLOW_CIDRS)"
CONTROL_PLANE_TUNNEL_PORT=''
[[ "$LAYER" != tls ]] || CONTROL_PLANE_TUNNEL_PORT="$(control_value CONTROL_PLANE_TUNNEL_PORT)"
ENABLE_HTTPS="$(deployment_value ENABLE_HTTPS)"
PUBLIC_APP_BASE_URL="$(deployment_value PUBLIC_APP_BASE_URL)"
exec 3</dev/tty
state=off; default=N
if [[ "$CONTROL_PLANE_PROXY" == true ]]; then state=on; default=Y; fi
say "Current website access: $state ($PUBLIC_APP_BASE_URL/control/)"
say "Allowed addresses: ${CONTROL_PLANE_ALLOW_CIDRS:-any}"
if [[ "$LAYER" == tls ]]; then say "SSH tunnel loopback port: ${CONTROL_PLANE_TUNNEL_PORT:-off}"; fi
if [[ "$LAYER" != tls && "$ENABLE_HTTPS" != true ]]; then
  echo 'Warning: over plain HTTP, the superadmin password and MFA code cross the network unencrypted.'
fi
question ANSWER 'Reach the control panel (/control/) through the website?' "$default" choices:Y,y,yes,YES,N,n,no,NO
NEW_PROXY=false; MODE=off; NEW_CIDRS=''; NEW_PORT=''
if [[ "$ANSWER" =~ ^[Yy] ]]; then
  NEW_PROXY=true; MODE=on
  if [[ "$LAYER" == none && "$ENABLE_HTTPS" == true ]]; then
    echo 'Restrict /control/ in your own proxy instead.'
  else
    question NEW_CIDRS "Allowed client IPs/CIDRs, space-separated (current: ${CONTROL_PLANE_ALLOW_CIDRS:-any}; blank = any)" '' cidrs
  fi
fi
if [[ "$LAYER" == tls ]]; then
  while true; do
    question NEW_PORT "Loopback port for an SSH-tunnel fallback (current: ${CONTROL_PLANE_TUNNEL_PORT:-off}; blank = off)" '' port
    if [[ -n "$NEW_PORT" ]] && control_plane_port_reserved "$NEW_PORT"; then
      echo 'That port is already used by the website or storage. Choose another port.'
    else
      break
    fi
  done
  if [[ -n "$NEW_PORT" ]]; then require_tunnel_engine || exit 64; fi
fi
if [[ "$NEW_PROXY" == "$CONTROL_PLANE_PROXY" && "$NEW_CIDRS" == "$CONTROL_PLANE_ALLOW_CIDRS" \
  && "$NEW_PORT" == "$CONTROL_PLANE_TUNNEL_PORT" ]]; then
  say 'No change; nothing applied.'
  exit 0
fi
say "New website access: $MODE ($PUBLIC_APP_BASE_URL/control/)"
say "Allowed addresses: ${NEW_CIDRS:-any}"
if [[ "$LAYER" == tls ]]; then say "SSH tunnel loopback port: ${NEW_PORT:-off}"; fi
question CONFIRM 'Apply now? Services restart briefly; the database is not touched.' Y choices:Y,y,yes,YES,N,n,no,NO
if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then say 'Nothing changed.'; exit 0; fi
exec 3<&-
arguments=(--control-plane "$MODE")
[[ "$MODE" != on ]] || arguments+=(--allow-cidrs "$NEW_CIDRS")
[[ -z "$NEW_PORT" ]] || arguments+=(--tunnel-port "$NEW_PORT")
exec bash "$ROOT/scripts/apply-settings.sh" "${arguments[@]}"
