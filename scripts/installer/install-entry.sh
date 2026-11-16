#!/usr/bin/env bash
# Stage 2 of the installer. It runs from the VERIFIED release bundle that the release asset
# install.sh downloaded, checked against SHA256SUMS and extracted; it never downloads release
# code itself. It owns the option checks, the questionnaire and the host setup.
set +x
set -euo pipefail
# One brace group: the whole file is parsed before any of it runs.
{
[[ -n "${SPACEWORKS_STAGED_DIR:-}" && -d "$SPACEWORKS_STAGED_DIR/runtime" ]] || {
  echo 'This script is part of the SpaceWorks release bundle; start from the release install.sh.' >&2; exit 64; }
(( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4) )) || {
  echo 'SpaceWorks requires Bash 4.4+; macOS needs modern Bash and Docker Desktop.' >&2; exit 64;
}
REPO_ARG=''; ANSWERS_ARG=''; INSTALL_RESUME=0; SETUP_NON_INTERACTIVE=0; PROFILE_ARG=''; ALLOW_PYTHON_BOOTSTRAP=0; PIN_ARG=''; DRY_RUN=0
usage() { echo 'Run install.sh --help for the options (docs/install-and-update.md).'; }
while (($#)); do
  case "$1" in
    --repo|--answers-file|--profile|--frontend|--version)
      (($# > 1)) || { echo "Missing value for $1." >&2; exit 64; }
      case "$1" in
        --repo) REPO_ARG="$2" ;; --answers-file) ANSWERS_ARG="$2" ;; --profile) PROFILE_ARG="$2" ;;
        --frontend) SPACEWORKS_FRONTEND="$2" ;; --version) PIN_ARG="$2" ;;
      esac
      shift ;;
    --repo=*) REPO_ARG="${1#*=}" ;;
    --profile=*) PROFILE_ARG="${1#*=}" ;;
    --frontend=*) SPACEWORKS_FRONTEND="${1#*=}" ;;
    --version=*) PIN_ARG="${1#*=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --non-interactive) SETUP_NON_INTERACTIVE=1 ;;
    --resume) INSTALL_RESUME=1 ;;
    --bootstrap-python) ALLOW_PYTHON_BOOTSTRAP=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo 'Unknown installer option; see install.sh --help.' >&2; exit 64 ;;
  esac
  shift
done
[[ -z "$PROFILE_ARG" ]] || SPACEWORKS_DEPLOYMENT_PROFILE="$PROFILE_ARG"
case "${SPACEWORKS_FRONTEND:-}" in
  '') ;;
  full|api-only) export SPACEWORKS_FRONTEND ;;
  *) echo 'Use --frontend full (web app + API) or --frontend api-only.' >&2; exit 64 ;;
esac
case "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" in
  full) ;;
  free) export SPACEWORKS_DEPLOYMENT_PROFILE ;;
  *) echo 'Use --profile full (default) or --profile free.' >&2; exit 64 ;;
esac
if [[ -n "$PIN_ARG" ]]; then
  [[ "$PIN_ARG" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-main\.[0-9]+\.[0-9a-f]{12})?$ ]] \
    || { echo 'Use --version X.Y.Z or X.Y.Z-main.<run>.<12-hex sha> (a published release).' >&2; exit 64; }
  PIN_ARG="${PIN_ARG#v}"
fi
if [[ "$INSTALL_RESUME" == 1 && ( -n "$PIN_ARG" || "$DRY_RUN" == 1 ) ]]; then
  echo '--resume continues the journaled release; it cannot be combined with --version or --dry-run.' >&2; exit 64
fi
[[ -z "$ANSWERS_ARG" || "$SETUP_NON_INTERACTIVE" == 1 ]] || { echo '--answers-file requires --non-interactive.' >&2; exit 64; }
[[ -z "$ANSWERS_ARG" || "$ANSWERS_ARG" == /* ]] || ANSWERS_ARG="$PWD/$ANSWERS_ARG"; [[ -z "$ANSWERS_ARG" || -f "$ANSWERS_ARG" ]] || { echo "Answers file $ANSWERS_ARG does not exist." >&2; exit 64; }
REPOSITORY="${REPO_ARG:-${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}}"
INSTALL_DIR="${SPACEWORKS_DIR:-/opt/spaceworks}"
if [[ "$INSTALL_DIR" =~ ^[A-Za-z]:[/\\] ]]; then
  command -v cygpath >/dev/null 2>&1 || { echo 'Use a native absolute installation path.' >&2; exit 64; }
  INSTALL_DIR="$(cygpath -u "$INSTALL_DIR")"
fi
[[ "$INSTALL_DIR" == /* ]] || INSTALL_DIR="$PWD/$INSTALL_DIR"
export SPACEWORKS_DIR="$INSTALL_DIR"
case "$INSTALL_DIR" in
  /|*"'"*|*$'\n'*|*/../*|*/./*|*/..|*/.) echo 'Use a canonical dedicated installation directory.' >&2; exit 64 ;;
esac
[[ ! -L "$INSTALL_DIR" ]] || { echo 'The install directory cannot be a symlink.' >&2; exit 64; }
# A fresh unattended install needs its answers; an existing install updates without them.
if [[ "$SETUP_NON_INTERACTIVE" == 1 && -z "$ANSWERS_ARG" && "$INSTALL_RESUME" != 1 && "$DRY_RUN" != 1 \
      && "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" != free && ! -f "$INSTALL_DIR/.spaceworks-version" ]]; then
  echo '--non-interactive requires --answers-file for a new install.' >&2; exit 64
fi
# Decision 220(a): new installs are Linux/macOS. Existing native Windows installs keep their menu.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    [[ -f "$INSTALL_DIR/.spaceworks-version" ]] || {
      echo 'The installer supports Linux and macOS. On Windows, run it inside WSL2 (Ubuntu) or a Linux VM; setup.ps1 is only a developer helper.' >&2
      exit 64; } ;;
esac
if [[ -d "$INSTALL_DIR" && "$(uname -s)" == Linux ]]; then
  owner="$(stat -c %u "$INSTALL_DIR")"
  [[ "$owner" == 0 || "$owner" == "$(id -u)" ]] || { echo 'Run the installer as the existing installation owner.' >&2; exit 64; }
fi
if [[ -z "$REPO_ARG" && -z "${SPACEWORKS_REPOSITORY:-}" && -f "$INSTALL_DIR/.env" ]]; then
  saved="$(sed -n 's/^SPACEWORKS_REPOSITORY=//p' "$INSTALL_DIR/.env" | tr -d '\r')"
  saved="${saved#\'}"; saved="${saved%\'}"; saved="${saved#\"}"; saved="${saved%\"}"
  REPOSITORY="${saved:-$REPOSITORY}"
fi
# The frontend mode is chosen at first install only; refuse a contradicting --frontend.
if [[ -n "${SPACEWORKS_FRONTEND:-}" && -f "$INSTALL_DIR/.env" ]]; then
  installed="$(sed -n 's/^SPACEWORKS_RUN_FRONTEND=//p' "$INSTALL_DIR/.env" | tr -d "\r'\"")"
  [[ "$installed" == no && "$SPACEWORKS_FRONTEND" == api-only || "$installed" != no && "$SPACEWORKS_FRONTEND" == full ]] \
    || { echo 'This install already has a frontend mode; --frontend cannot change it.' >&2; exit 64; }
fi
[[ "$REPOSITORY" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}$ \
   && "$REPOSITORY" != */. && "$REPOSITORY" != */.. ]] || { echo 'Invalid GitHub owner/repository.' >&2; exit 64; }
export SPACEWORKS_REPOSITORY="$REPOSITORY" SPACEWORKS_INSTALL_REPOSITORY_PINNED=1
# Piped from curl, stdin is the script: questions come from the terminal (/dev/tty).
TTY_INPUT=/dev/tty
[[ "${SPACEWORKS_INSTALL_TEST_MODE:-}" != 1 ]] || TTY_INPUT="${SPACEWORKS_INSTALL_TEST_TTY:-/dev/tty}"
if [[ "$SETUP_NON_INTERACTIVE" == 0 ]] && ! { : < "$TTY_INPUT"; } 2>/dev/null; then
  echo 'No terminal is available to answer the installer questions (for example in CI, cron or a' >&2
  echo 'non-interactive SSH session). Run it from an interactive terminal, or pass' >&2
  echo '--non-interactive --answers-file <private.json> (see install.sh --help). Nothing was changed.' >&2
  exit 64
fi
if [[ "$DRY_RUN" == 1 ]]; then
  export SPACEWORKS_INSTALL_DRY_RUN=1
  echo '[SpaceWorks installer] Dry run: checks and plan only; nothing is installed, written or started.'
fi
INSTALL_MENU_CHOICE=''
if [[ "$DRY_RUN" == 1 && -f "$INSTALL_DIR/.spaceworks-version" ]]; then
  INSTALL_MENU_CHOICE=1
elif [[ "$SETUP_NON_INTERACTIVE" == 0 && "$INSTALL_RESUME" == 0 && -f "$INSTALL_DIR/.spaceworks-version" ]]; then
  printf '%s\n' 'SpaceWorks is already installed here. What would you like to do?' \
    '  1) Update to this release          2) Change which areas are switched on   3) Both' \
    '  4) Cancel - change nothing          5) Set up automatic deploys (GitHub runner)' \
    '  6) Turn web access to the control panel (/control/) on or off'     '  7) Change outside services (database, Redis, storage, email)' >&2
  printf 'Choose 1-7 [4]: ' >&2
  IFS= read -r INSTALL_MENU_CHOICE < "$TTY_INPUT" || exit 1
  INSTALL_MENU_CHOICE="${INSTALL_MENU_CHOICE:-4}"
  case "$INSTALL_MENU_CHOICE" in
    1|3) ;;
    2) (cd "$INSTALL_DIR" && SPACEWORKS_UPDATE_INSTALL_DIR="$INSTALL_DIR" bash scripts/update.sh --modules-only); exit $? ;;
    5) (cd "$INSTALL_DIR" && bash scripts/install-runner.sh); exit $? ;;
    6) (cd "$INSTALL_DIR" && bash scripts/control-plane-settings.sh); exit $? ;;
    7) (cd "$INSTALL_DIR" && bash scripts/switch-services.sh menu); exit $? ;;
    4) echo 'Cancelled; existing deployment was not changed.'; exit 130 ;;
    *) echo 'Invalid menu choice.' >&2; exit 64 ;;
  esac
fi
if ! python3 -I -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1 \
  && python -I -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
  SPACEWORKS_INSTALL_PYTHON="$(command -v python)"; export SPACEWORKS_INSTALL_PYTHON
  python3() { "$SPACEWORKS_INSTALL_PYTHON" "$@"; }
  export -f python3
fi
if ! command -v python3 >/dev/null 2>&1; then
  [[ "$(uname -s)" == Linux && "$DRY_RUN" != 1 ]] || {
    echo 'Install Python 3.10+ and rerun; no installation state changed.' >&2; exit 64;
  }
  if [[ "$ALLOW_PYTHON_BOOTSTRAP" != 1 ]]; then
    [[ "$SETUP_NON_INTERACTIVE" != 1 ]] || { echo 'Preinstall Python 3.10+ or explicitly pass --bootstrap-python.' >&2; exit 64; }
    printf 'Install Python 3 to continue the installation? [y/N]: ' >/dev/tty
    IFS= read -r answer </dev/tty || exit 1
    [[ "$answer" =~ ^[Yy]$ ]] || exit 130
  fi
  bootstrap_sudo=(); [[ "$(id -u)" == 0 ]] || bootstrap_sudo=(sudo)
  if command -v apt-get >/dev/null 2>&1; then
    "${bootstrap_sudo[@]}" apt-get update
    "${bootstrap_sudo[@]}" apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then "${bootstrap_sudo[@]}" dnf install -y python3
  else echo 'Install Python 3.10+ with the native package manager, then rerun.' >&2; exit 64; fi
fi
python3 -I -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || { echo 'Python 3.10+ required.' >&2; exit 64; }
# Forward-only (decision 219g): never hand an existing install to an older release's tooling.
installed_version=''
if [[ -f "$INSTALL_DIR/.spaceworks-version" ]]; then
  installed_version="$(tr -d '[:space:]' 2>/dev/null < "$INSTALL_DIR/.spaceworks-version" || true)"
fi
refuse_older_release() {
  [[ -n "$installed_version" ]] || return 0
  python3 -I -c '
import re, sys
def key(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-main\.(\d+)\.[0-9a-f]{12})?", value)
    return tuple(int(part) for part in match.groups() if part is not None) if match else None
installed, selected = key(sys.argv[1]), key(sys.argv[2])
sys.exit(3 if installed and selected and selected < installed[:len(selected)] else 0)' "$installed_version" "$1" && return 0
  echo "[SpaceWorks installer] Refusing $1: $installed_version is installed and upgrades are forward-only." >&2
  echo '[SpaceWorks installer] To go back, restore the pre-upgrade backup in backups/ (docs/install-and-update.md#rolling-back). Nothing was changed.' >&2
  exit 64
}
BOOTSTRAP_STAGE="$SPACEWORKS_STAGED_DIR"
trap 'rm -rf -- "$BOOTSTRAP_STAGE"' EXIT
STAGE_DIR="$BOOTSTRAP_STAGE/runtime"; ARCHIVE=''
VERSION="$SPACEWORKS_STAGED_VERSION"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-main\.[0-9]+\.[0-9a-f]{12})?$ ]] || { echo 'Invalid staged release version.' >&2; exit 64; }
[[ -z "$PIN_ARG" || "$VERSION" == "$PIN_ARG" || "$VERSION" == "$PIN_ARG"-main.* ]] \
  || { echo "The staged release $VERSION differs from --version $PIN_ARG." >&2; exit 64; }
refuse_older_release "$VERSION"
# The bundle arrived verified (SHA256SUMS, and cosign when present); record what was checked.
python3 -I - "$STAGE_DIR/.spaceworks-release.json" "$REPOSITORY" "$VERSION" "$SPACEWORKS_STAGED_COMMIT" \
  "$SPACEWORKS_STAGED_SHA256" <<'PY'
import json, sys
path, repo, version, commit, digest = sys.argv[1:]
with open(path, "w") as out:
    out.write(json.dumps({"schema_version": 1, "repository": repo, "release": version,
                          "commit": commit, "archive_sha256": digest}) + "\n")
PY
if [[ -n "${SPACEWORKS_INSTALL_LOG:-}" && "${SPACEWORKS_INSTALL_TEST_MODE:-}" != 1 ]]; then
  exec > >(tee -a "$SPACEWORKS_INSTALL_LOG") 2>&1
fi
die() { echo "[SpaceWorks installer] $*" >&2; exit 1; }
if [[ "$DRY_RUN" == 1 ]] && ! grep -q SPACEWORKS_INSTALL_DRY_RUN "$STAGE_DIR/scripts/installer/install-runtime.sh"; then
  die "Release $VERSION predates --dry-run; nothing was changed."
fi
source "$STAGE_DIR/scripts/install-host-bundle.sh"
validate_host_bundle "$STAGE_DIR"
source "$STAGE_DIR/scripts/installer/install-runtime.sh"
exit
}
