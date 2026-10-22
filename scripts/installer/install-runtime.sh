#!/usr/bin/env bash
# Verified host preflight and dependency admission, sourced by install.sh.
set -euo pipefail
# One command for everyone: --repo (or SPACEWORKS_REPOSITORY) picks a fork up front;
# otherwise a fresh install asks below, defaulting to the main project.
[[ -z "$REPO_ARG" ]] || SPACEWORKS_REPOSITORY="$REPO_ARG"
REPOSITORY="${SPACEWORKS_REPOSITORY:-SpaceWorks-HQ/SpaceWorks}"
INSTALL_DIR="${SPACEWORKS_DIR:-/opt/spaceworks}"
MIN_FREE_KB=$((8 * 1024 * 1024))
RUN_ROOT=()
SUDO=()
USE_DOCKER_GROUP=0
RUN_INSTALLED_AS_ROOT=0
ACTION=fresh
RELEASE_TAG="v$VERSION"


CREATED_PARENT=0
say() { printf '[SpaceWorks installer] %s\n' "$*"; }
die() { printf '[SpaceWorks installer] ERROR: %s\n' "$*" >&2; exit 1; }
prompt() {
  local reply
  [[ -r /dev/tty ]] || die "An interactive terminal is required."
  printf '%s' "$1" > /dev/tty
  IFS= read -r reply < /dev/tty || return 1
  printf '%s' "${reply%$'\r'}"
}
cleanup() {
  [[ -z "${BOOTSTRAP_STAGE:-}" ]] || rm -rf -- "$BOOTSTRAP_STAGE"
  [[ -z "$ARCHIVE" ]] || rm -f -- "$ARCHIVE"
  if [[ "$CREATED_PARENT" == 1 ]]; then
    ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} rmdir -- "$(dirname "$INSTALL_DIR")" 2>/dev/null || true
  fi
}
trap cleanup EXIT
case "$INSTALL_DIR" in
  ""|/|*"'"*|*$'\n'*) die "SPACEWORKS_DIR must be a specific path without single quotes or newlines." ;;
esac
while [[ "$INSTALL_DIR" == */ ]]; do INSTALL_DIR="${INSTALL_DIR%/}"; done
[[ -n "$INSTALL_DIR" ]] || die "SPACEWORKS_DIR cannot be the filesystem root."
[[ "$INSTALL_DIR" == /* ]] || INSTALL_DIR="$PWD/$INSTALL_DIR"
source "$STAGE_DIR/scripts/installer/host-paths.sh"
validate_host_path "$INSTALL_DIR" || die 'The install directory is not canonical or has unsafe ownership.'
say "Preflight only—nothing will be installed until all checks pass."
say "Checking architecture, operating system, dependencies, Docker, release availability, ports, disk space, and existing state."
source "$STAGE_DIR/scripts/installer/host-preflight.sh"
if ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} test -f "$INSTALL_DIR/.spaceworks-version"; then
  if [[ -n "${INSTALL_MENU_CHOICE:-}" ]]; then ACTION="$INSTALL_MENU_CHOICE"
  elif [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 ]]; then ACTION=1; else
  ACTION="$(prompt "
SpaceWorks is already installed in $INSTALL_DIR (version $(${RUN_ROOT[@]+"${RUN_ROOT[@]}"} cat "$INSTALL_DIR/.spaceworks-version" 2>/dev/null || echo unknown)).
What do you want to do?
  1) Update to the latest release - backs up the database, moves to the newest main
     release, runs migrations and restarts. Your modules and data stay as they are.
  2) Change modules only - turn optional modules (events, bookings, machines, membership,
     payments...) on or off. No new version is downloaded.
  3) Update, then change modules - option 1 followed by option 2.
  4) Cancel - exit without changing anything.
  5) Install or re-register the GitHub Actions runner only.
  6) Turn web access to the control plane (/control/) on or off - no new version is
     downloaded.
Choose 1-6 [4]: ")"
  fi
  ACTION="${ACTION:-4}"
  case "$ACTION" in
    1) ACTION=update ;;
    2) ACTION=modules ;;
    3) ACTION=both ;;
    5) ACTION=runner ;;
    6) ACTION=controlplane ;;
    4) say "Cancelled; existing deployment was not changed."; exit 130 ;;
    *) die "Invalid menu choice; existing deployment was not changed." ;;
  esac
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} test -f "$INSTALL_DIR/scripts/update.sh" || die "The version marker exists but scripts/update.sh is missing. Repair the install manually."
  if [[ "$(id -u)" != 0 ]] && { [[ ! -w "$INSTALL_DIR" ]] \
    || { [[ "$HOST_KIND" == linux ]] && [[ "$(stat -c %u "$INSTALL_DIR")" == 0 ]]; }; }; then
    command -v sudo >/dev/null 2>&1 || die "The existing install is not writable and sudo is unavailable."
    RUN_ROOT=(sudo)
    RUN_INSTALLED_AS_ROOT=1
  fi
elif ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} test -e "$INSTALL_DIR"; then
  if ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} test -d "$INSTALL_DIR" && [[ -z "$(${RUN_ROOT[@]+"${RUN_ROOT[@]}"} find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    EMPTY_INSTALL_DIR=1
  else
    if [[ "${INSTALL_RESUME:-0}" == 1 && -f "$INSTALL_DIR/.spaceworks-install.json" ]]; then
      python3 "$STAGE_DIR/scripts/installer/state.py" validate --root "$INSTALL_DIR" --repository "$REPOSITORY" --release "$VERSION" || die 'Unsafe incomplete installation.'
      ACTION=resume
    else
      die "$INSTALL_DIR contains state without a completed version marker. Use --resume only for a verified incomplete install."
    fi
  fi
else
  EMPTY_INSTALL_DIR=0
fi
if [[ "$ACTION" == runner ]]; then
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} test -f "$INSTALL_DIR/scripts/install-runner.sh" \
    || die 'This installation needs a release update before installing its runner.'
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} bash "$INSTALL_DIR/scripts/install-runner.sh"
  exit 0
fi
if [[ "$ACTION" == controlplane ]]; then
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} test -f "$INSTALL_DIR/scripts/control-plane-settings.sh" \
    || die 'This installation needs a release update (option 1) before it can change control-plane access.'
  # RUN_ROOT may only mean "the parent is unwritable"; a user-owned install must run as its owner.
  cp_runner=()
  [[ "$RUN_INSTALLED_AS_ROOT" != 1 ]] || cp_runner=(${RUN_ROOT[@]+"${RUN_ROOT[@]}"})
  ${cp_runner[@]+"${cp_runner[@]}"} bash "$INSTALL_DIR/scripts/control-plane-settings.sh" </dev/tty || exit $?
  exit 0
fi
port_in_use() {
  local port="$1" hex file
  if [[ "$HOST_KIND" == linux ]]; then
    printf -v hex '%04X' "$port"
    for file in /proc/net/tcp /proc/net/tcp6; do
      [[ -r "$file" ]] || continue
      awk -v wanted="$hex" 'NR > 1 { split($2, address, ":"); if (toupper(address[2]) == wanted && $4 == "0A") exit 7 }' "$file" || return 0
    done
    return 1
  fi
  netstat -an 2>/dev/null | awk -v pattern="[:.]${port}[[:space:]]" \
    'toupper($0) ~ /LISTEN/ && $0 ~ pattern { found=1 } END { exit !found }'
}
disk_path="$INSTALL_DIR"
while [[ ! -e "$disk_path" && "$disk_path" != / ]]; do disk_path="$(dirname "$disk_path")"; done
available_kb="$(df -Pk "$disk_path" | awk 'NR == 2 {print $4}')"
[[ "$available_kb" =~ ^[0-9]+$ ]] || die "Could not determine free disk space for $INSTALL_DIR."
((available_kb >= MIN_FREE_KB)) || die "At least 8 GiB free is required; $disk_path has $((available_kb / 1024)) MiB."
say "Disk-space check passed."
say "Using verified release $VERSION ($REPOSITORY)."
if [[ "$ACTION" == fresh ]]; then
  source "$STAGE_DIR/scripts/setup-questions.sh"
  SETUP_HOST_PLAN="install/ensure ${missing[*]:-no missing packages}; enable Docker/access if needed; install $RELEASE_TAG in $INSTALL_DIR; write private settings; pull images; initialize database; create your admin/makerspace; apply selected modules; start selected services; install the optional GitHub Actions runner"
  if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 && "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" != free ]]; then
    ROOT="$STAGE_DIR"
    load_noninteractive_answers "$ANSWERS_ARG" || exit $?
  fi
  ask_setup_questions || exit $?
fi
if [[ "$ACTION" == fresh && "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" == free ]]; then
  # Opt-in free profile: setup writes its private environment only and claims no
  # host ports or services on this server.
  say "Free profile selected; setup will write its private environment and start nothing."
elif [[ "$ACTION" == fresh ]]; then
  persist_setup_answers "$STAGE_DIR/.spaceworks-answers"
  ports=()
  if [[ "$HTTPS_MODE" == 2 ]]; then ports+=(80 443)
  elif [[ "$HTTPS_MODE" == 3 ]]; then ports+=(8080)
  else ports+=(80); fi
  [[ "$STORAGE" != 1 || "$HOSTING_MODEL" == 3 ]] || ports+=(9000 9001)
  if [[ "$HTTPS_MODE" == 2 && -n "${CONTROL_PLANE_TUNNEL_PORT:-}" ]]; then
    for port in "${ports[@]}"; do
      [[ "$port" != "$CONTROL_PLANE_TUNNEL_PORT" ]] || die "TCP port $port is already selected for another service. Choose a different SSH-tunnel port."
    done
    ports+=("$CONTROL_PLANE_TUNNEL_PORT")
  fi
  for port in "${ports[@]}"; do
    port_in_use "$port" && die "TCP port $port is already in use. Free it before installing."
  done
  say "Required TCP ports ${ports[*]} are free."
fi
source "$STAGE_DIR/scripts/installer/linux-dependencies.sh"

if ((${#missing[@]} > 0)); then install_linux_dependencies
elif [[ "${INSTALL_RUNNER:-N}" =~ ^[Yy] ]] && ! command -v python3 >/dev/null 2>&1; then
  install_linux_dependencies
fi
if ! docker compose version >/dev/null 2>&1; then
  plugin_stage="$(mktemp -d)"
  python3 "$STAGE_DIR/scripts/installer/compose-plugin.py" "$ARCH" "$plugin_stage" || die 'Could not verify Compose.'
  ${SUDO[@]+"${SUDO[@]}"} install -m 0755 -d /usr/local/lib/docker/cli-plugins
  ${SUDO[@]+"${SUDO[@]}"} install -m 0755 "$plugin_stage/compose-plugin" "/usr/local/lib/docker/cli-plugins/.docker-compose-$$"
  ${SUDO[@]+"${SUDO[@]}"} mv -f "/usr/local/lib/docker/cli-plugins/.docker-compose-$$" /usr/local/lib/docker/cli-plugins/docker-compose
  rm -rf -- "$plugin_stage"
fi
if ! docker info >/dev/null 2>&1; then
  if [[ "$HOST_KIND" == linux && -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
    ${SUDO[@]+"${SUDO[@]}"} systemctl enable --now docker || die 'Docker service failed to start.'
  fi
fi
if ! docker info >/dev/null 2>&1; then
  if [[ "$HOST_KIND" == linux && "$(id -u)" != 0 && ${#SUDO[@]} -gt 0 ]] && ${SUDO[@]+"${SUDO[@]}"} docker info >/dev/null 2>&1; then
    if [[ "$RUN_INSTALLED_AS_ROOT" == 0 ]]; then
      operator="$(id -un)"
      ${SUDO[@]+"${SUDO[@]}"} usermod -aG docker "$operator" \
        || die "Run sudo usermod -aG docker '$operator' (if the group is missing, run sudo groupadd docker first), sign out and back in, then rerun."
      command -v sg >/dev/null 2>&1 || die "Docker access needs refreshed group membership. Sign out, sign in, and rerun this installer."
      sg docker -c 'docker info >/dev/null 2>&1' || die "Docker is still inaccessible inside the docker group. Sign out and back in, test docker info, and rerun; if needed, configure Docker's socket group before retrying."
      USE_DOCKER_GROUP=1
      say "Added $operator to the docker group; setup will use that group for this run."
    fi
  else
    if [[ "$HOST_KIND" == linux && ! -d /run/systemd/system ]]; then
      die 'Non-systemd Linux requires an already-running Docker daemon. Start Docker using the operating system service manager, verify docker info as the install owner, then retry.'
    fi
    die "Docker is inaccessible. Run sudo systemctl start docker; then test sudo docker info. For user access, run sudo usermod -aG docker \$(id -un), sign out and back in, then rerun."
  fi
fi
docker compose version >/dev/null 2>&1 || die "Docker Compose V2 is still unavailable after dependency setup."
if [[ "$HOST_KIND" == linux && "$ACTION" == fresh ]]; then
  if [[ "$RUN_INSTALLED_AS_ROOT" == 1 ]]; then
    docker_root="$(${RUN_ROOT[@]+"${RUN_ROOT[@]}"} docker info --format '{{.DockerRootDir}}')"
  elif [[ "$USE_DOCKER_GROUP" == 1 ]]; then
    docker_root="$(sg docker -c "docker info --format '{{.DockerRootDir}}'")"
  else
    docker_root="$(docker info --format '{{.DockerRootDir}}')"
  fi
  [[ "$docker_root" == /* ]] || die 'Cannot verify Docker data-root capacity.'
  source "$STAGE_DIR/scripts/installer/capacity.sh"
  require_capacity "$MIN_FREE_KB" "$INSTALL_DIR" "$docker_root" "${SPACEWORKS_OPS_HOST_DIR:-/var/lib/spaceworks/ops}" || die 'Insufficient host capacity.'
fi
# Only now is Docker installed, running and reachable; read the engine as setup will use it.
if [[ "$ACTION" == fresh && "${HTTPS_MODE:-}" == 2 && -n "${CONTROL_PLANE_TUNNEL_PORT:-}" ]]; then
  if [[ "$RUN_INSTALLED_AS_ROOT" == 1 ]]; then
    engine="$(${RUN_ROOT[@]+"${RUN_ROOT[@]}"} docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
  elif [[ "$USE_DOCKER_GROUP" == 1 ]]; then
    engine="$(sg docker -c "docker version --format '{{.Server.Version}}'" 2>/dev/null || true)"
  else
    engine="$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
  fi
  source "$STAGE_DIR/scripts/compose-deployment.sh"
  require_tunnel_engine "$engine" || die 'Cannot install the control-plane SSH tunnel with this Docker Engine.'
fi
source "$STAGE_DIR/scripts/installer/install-finish.sh"
