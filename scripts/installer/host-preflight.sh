#!/usr/bin/env bash
# Read-only architecture, operating-system, privilege and dependency inventory.
machine="$(uname -m)"
case "$machine" in
  x86_64|amd64) ARCH=x86_64 ;;
  aarch64|arm64) ARCH=aarch64 ;;
  *) die "Unsupported architecture '$machine'. SpaceWorks release images support only x86_64 and aarch64." ;;
esac
kernel="$(uname -s)"
PACKAGE_FAMILY=""
case "$kernel" in
  Linux)
    [[ -r /etc/os-release ]] || die "Linux distribution metadata /etc/os-release is missing."
    # /etc/os-release is the distribution's canonical data source. Do not infer
    # the family from whichever package-manager binary happens to be present.
    # Read it in subshells: it also defines VERSION, NAME and more, and the pinned
    # release VERSION is already set when this runs.
    # shellcheck disable=SC1091
    ID="$(ID=''; source /etc/os-release; printf '%s' "${ID:-}")"
    # shellcheck disable=SC1091
    ID_LIKE="$(ID_LIKE=''; source /etc/os-release; printf '%s' "${ID_LIKE:-}")"
    distro_words=" ${ID:-} ${ID_LIKE:-} "
    case "$distro_words" in
      *" debian "*|*" ubuntu "*|*" linuxmint "*) PACKAGE_FAMILY=apt ;;
      *" fedora "*|*" rhel "*|*" centos "*|*" rocky "*|*" almalinux "*) PACKAGE_FAMILY=dnf ;;
      *" arch "*|*" manjaro "*) PACKAGE_FAMILY=pacman ;;
      *" suse "*|*" opensuse "*|*" sles "*) PACKAGE_FAMILY=zypper ;;
      *) die "Unsupported Linux distribution '${ID:-unknown}' (ID_LIKE='${ID_LIKE:-}'). Supported families: Debian/Ubuntu, RHEL/Fedora/Alma/Rocky, Arch, and SUSE." ;;
    esac
    HOST_KIND=linux
    ;;
  MINGW*|MSYS*|CYGWIN*) HOST_KIND=windows ;;
  Darwin) HOST_KIND=macos ;;
  *) die "Unsupported host '$kernel'. Use Linux, Windows Git Bash, or macOS with Docker Desktop." ;;
esac
say "Architecture: $ARCH; host: $HOST_KIND${PACKAGE_FAMILY:+/$PACKAGE_FAMILY}."
# Host privilege and install-directory privilege are independent decisions.
if [[ "$HOST_KIND" == linux && "$(id -u)" != 0 ]]; then
  command -v sudo >/dev/null 2>&1 && SUDO=(sudo)
  # Releases stage beside the install, including on a user-owned /opt rerun.
  write_path="$(dirname "$INSTALL_DIR")"
  while [[ ! -e "$write_path" ]]; do write_path="$(dirname "$write_path")"; done
  if [[ ! -w "$write_path" || ( -d "$INSTALL_DIR" && ! -x "$INSTALL_DIR" ) ]]; then
    ((${#SUDO[@]} > 0)) || die "Writing $INSTALL_DIR requires sudo. Install sudo or run this installer as root."
    RUN_ROOT=(sudo)
  fi
elif [[ "$(id -u)" == 0 ]]; then
  RUN_INSTALLED_AS_ROOT=1
fi
missing=()
MISSING_DOCKER=0
MISSING_COMPOSE=0
command -v curl >/dev/null 2>&1 || missing+=(curl)
command -v tar >/dev/null 2>&1 || missing+=(tar)
if [[ "$HOST_KIND" == linux ]] && ! command -v flock >/dev/null 2>&1; then missing+=(util-linux); fi
if ! command -v docker >/dev/null 2>&1; then
  missing+=(docker-engine docker-compose-v2)
  MISSING_DOCKER=1
  MISSING_COMPOSE=1
elif ! docker compose version >/dev/null 2>&1; then
  missing+=(docker-compose-v2)
  MISSING_COMPOSE=1
fi
if ((${#missing[@]} > 0)); then
  if [[ "$HOST_KIND" != linux ]]; then
    die "Missing: ${missing[*]}. Install Docker Desktop (with Compose V2), curl, and tar, then rerun."
  fi
  if [[ "$(id -u)" != 0 ]]; then
    ((${#SUDO[@]} > 0)) || die "Missing ${missing[*]} and sudo is unavailable. Install them as root, then rerun."
  fi
  say "After preflight, the $PACKAGE_FAMILY family installer will install/ensure: curl, tar, Docker Engine, and Docker Compose V2."
else
  say "Dependencies are already present."
fi
# Memory is advisory: the full stack (database, Redis, storage, API, worker, scheduler,
# website) wants about 4 GiB; smaller hosts may work with swap but start slowly.
memory_kb=''
if [[ "$HOST_KIND" == linux && -r /proc/meminfo ]]; then
  memory_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
elif [[ "$HOST_KIND" == macos ]]; then
  memory_kb="$(sysctl -n hw.memsize 2>/dev/null || true)"; [[ ! "$memory_kb" =~ ^[0-9]+$ ]] || memory_kb=$((memory_kb / 1024))
fi
if [[ "$memory_kb" =~ ^[0-9]+$ ]] && ((memory_kb > 0 && memory_kb < 3584 * 1024)); then
  say "Warning: $((memory_kb / 1024)) MiB RAM detected; about 4 GiB is recommended (2 GiB plus swap is the floor). Expect slow starts."
fi
if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
  if [[ "$HOST_KIND" == linux ]]; then
    say "Docker is installed but stopped/inaccessible; after preflight the installer will start it or configure docker-group access."
  else
    die "Docker Desktop is installed but not running. Start it and wait until it is ready, then rerun; no state was changed."
  fi
fi
