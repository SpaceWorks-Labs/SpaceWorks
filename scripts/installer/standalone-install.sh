#!/bin/sh
# SpaceWorks installer. Published with every release as the asset `install.sh`:
#
#   curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh
#
# It checks the host, downloads the release bundle, verifies it against the release's
# SHA256SUMS (and its cosign signature when cosign is installed), and only then runs the
# installer tooling that arrived inside that verified bundle. It never runs unverified code.
# The whole body is one function so a truncated download runs nothing.

main() {
  set -eu
  BASE=https://github.com; API=https://api.github.com
  DEFAULT_REPO=SpaceWorks-Labs/SpaceWorks
  INSTALL_DIR="${SPACEWORKS_DIR:-/opt/spaceworks}"
  VERSION_ARG="${SPACEWORKS_VERSION:-}"; REPO="${SPACEWORKS_REPOSITORY:-}"
  DRY=0; UNINSTALL=0; PURGE=0; NONINT=0; STEP=0; TOTAL=6; STAGE=''; LOG_FILE=''
  if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD=$(printf '\033[1m'); RED=$(printf '\033[31m'); YEL=$(printf '\033[33m'); OFF=$(printf '\033[0m')
  else BOLD=''; RED=''; YEL=''; OFF=''; fi

  logf() { if [ -n "$LOG_FILE" ]; then printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_FILE" 2>/dev/null || true; fi; }
  step() { STEP=$((STEP + 1)); printf '%s[%s/%s]%s %s\n' "$BOLD" "$STEP" "$TOTAL" "$OFF" "$*"; logf "STEP $*"; }
  say() { printf '      %s\n' "$*"; logf "$*"; }
  warn() { printf '      %swarning:%s %s\n' "$YEL" "$OFF" "$*" >&2; logf "WARN $*"; }
  fail() { printf '%serror:%s %s\n' "$RED" "$OFF" "$*" >&2; logf "ERROR $*"; exit 1; }
  need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is required; install it and run the installer again."; }
  # shellcheck disable=SC2329  # invoked through trap
  cleanup() { if [ -n "$STAGE" ]; then rm -rf -- "$STAGE"; fi; }

  usage() {
    cat <<'EOF'
SpaceWorks installer - installs or updates SpaceWorks on this server.

  curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh
  curl -fsSL .../install.sh | sh -s -- --frontend api-only       # options go after `sh -s --`

With no options it asks a few questions (press Enter for the suggested answer), installs,
and finishes by printing the address to open and where the log is. Running it again updates.

Options:
  --version X.Y.Z[-main.N.sha]  Install that release instead of the latest (or SPACEWORKS_VERSION).
                                An older version than the installed one is refused (forward-only).
  --frontend full|api-only      Full = web app + API; api-only = backend for apps and integrations.
  --dry-run                     Check this host and show the plan; install and start nothing.
  --non-interactive             Do not ask questions; needs --answers-file for a new install.
  --answers-file FILE           Private (mode 0600) JSON file with the answers.
  --repo OWNER/NAME             Install from a fork (or SPACEWORKS_REPOSITORY).
  --uninstall [--purge]         Remove the services; keep your data and backups. --purge also
                                deletes local volumes and asks you to confirm by typing a phrase.
  -h, --help                    Show this help.

SPACEWORKS_DIR sets the install directory (default /opt/spaceworks). Needs Linux or macOS
(Windows: use WSL2), Docker with Compose v2, curl, tar, 10 GB free disk and 2 GB RAM.
Guide: https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/install-and-update.md
EOF
  }

  # Arguments are scanned here only for what this stage needs; all are passed on unchanged.
  want=''
  for arg in "$@"; do
    if [ -n "$want" ]; then
      if [ "$want" = version ]; then VERSION_ARG=$arg; else REPO=$arg; fi
      want=''; continue
    fi
    case $arg in
      -h|--help) usage; exit 0 ;;
      --version) want=version ;; --version=*) VERSION_ARG=${arg#*=} ;;
      --repo) want=repo ;; --repo=*) REPO=${arg#*=} ;;
      --dry-run) DRY=1 ;; --non-interactive) NONINT=1 ;;
      --uninstall) UNINSTALL=1 ;; --purge) PURGE=1 ;;
    esac
  done
  [ -z "$want" ] || fail "Missing value for --$want."
  if [ -z "$REPO" ] && [ -f "$INSTALL_DIR/.env" ]; then
    REPO=$(sed -n 's/^SPACEWORKS_REPOSITORY=//p' "$INSTALL_DIR/.env" | tr -d "\r'\"")
  fi
  REPO=${REPO:-$DEFAULT_REPO}
  printf '%s' "$REPO" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+$' || fail 'Invalid GitHub owner/repository.'
  case $REPO in *..*) fail 'Invalid GitHub owner/repository.' ;; esac
  case $INSTALL_DIR in /|*"'"*) fail 'Use a dedicated installation directory (SPACEWORKS_DIR).' ;; esac
  if [ -n "$VERSION_ARG" ]; then
    printf '%s' "$VERSION_ARG" | grep -Eq '^v?[0-9]+\.[0-9]+\.[0-9]+(-main\.[0-9]+\.[0-9a-f]{12})?$' \
      || fail 'Use --version X.Y.Z (or the full X.Y.Z-main.<run>.<sha> of a published release).'
    VERSION_ARG=${VERSION_ARG#v}
  fi
  if [ -d "$INSTALL_DIR" ] && [ -w "$INSTALL_DIR" ]; then LOG_FILE="$INSTALL_DIR/install.log"
  else LOG_FILE="${TMPDIR:-/tmp}/spaceworks-install-$$.log"; fi
  : > "$LOG_FILE" 2>/dev/null || LOG_FILE=''

  if [ "$UNINSTALL" = 1 ]; then
    [ -f "$INSTALL_DIR/scripts/uninstall.sh" ] || fail "No SpaceWorks install found in $INSTALL_DIR."
    need bash
    if [ "$PURGE" = 1 ]; then
      phrase="DELETE-LOCAL-DATA:$(basename "$INSTALL_DIR")"
      [ "$NONINT" = 0 ] || fail '--purge needs a person at a terminal to confirm; it cannot run with --non-interactive.'
      printf 'This permanently deletes the local database and file volumes of %s.\nBackups in %s/backups are kept.\nType %s to continue: ' \
        "$INSTALL_DIR" "$INSTALL_DIR" "$phrase" > /dev/tty
      read -r typed < /dev/tty || fail 'No terminal is available to confirm.'
      [ "$typed" = "$phrase" ] || fail 'Confirmation did not match; nothing was removed.'
      exec bash "$INSTALL_DIR/scripts/uninstall.sh" --purge-local-data --confirm "$typed"
    fi
    say 'Removing services and managed files. Data volumes, keys and backups are kept.'
    exec bash "$INSTALL_DIR/scripts/uninstall.sh"
  fi

  step 'Checking this server'
  case $(uname -s) in
    Linux) HOST=linux ;; Darwin) HOST=macos ;;
    MINGW*|MSYS*|CYGWIN*) fail 'Windows is not supported directly. Install WSL2 (Ubuntu) and run this command inside it.' ;;
    *) fail "Unsupported operating system $(uname -s); use Linux or macOS." ;;
  esac
  case $(uname -m) in x86_64|amd64|aarch64|arm64) ;; *) fail "Unsupported architecture $(uname -m); amd64 and arm64 are supported." ;; esac
  need curl; need tar; need bash
  if command -v sha256sum >/dev/null 2>&1; then SHA=sha256sum; elif command -v shasum >/dev/null 2>&1; then SHA='shasum -a 256'
  else fail 'sha256sum or shasum is required to verify the download.'; fi
  if ! command -v docker >/dev/null 2>&1; then
    [ "$HOST" = linux ] || fail 'Docker is not installed. Install Docker Desktop, start it, and run this again.'
    warn 'Docker is not installed; the next stage offers to install Docker Engine (needs sudo).'
  elif ! docker info >/dev/null 2>&1; then
    [ "$HOST" = linux ] || fail 'Docker is not running. Start Docker Desktop and run this again.'
    warn 'Docker is not reachable by this user (stopped, or it needs sudo/docker group); the next stage handles access.'
  elif ! docker compose version >/dev/null 2>&1; then
    [ "$HOST" = linux ] || fail 'Docker Compose v2 is missing. Update Docker Desktop and run this again.'
    warn 'Docker Compose v2 is missing; the next stage offers to install it.'
  fi
  probe=$INSTALL_DIR; while [ ! -e "$probe" ] && [ "$probe" != / ]; do probe=$(dirname "$probe"); done
  free_kb=$(df -Pk "$probe" | awk 'NR == 2 {print $4}')
  case $free_kb in ''|*[!0-9]*) fail "Could not measure free disk space for $INSTALL_DIR." ;; esac
  [ "$free_kb" -ge "${SPACEWORKS_MIN_FREE_KB:-10485760}" ] || fail "At least 10 GB of free disk is needed; $probe has $((free_kb / 1024)) MB."
  if [ "$HOST" = linux ]; then ram_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
  else ram_kb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 )); fi
  [ "${ram_kb:-0}" -ge 2000000 ] || warn 'Less than 2 GB of RAM detected; SpaceWorks may run slowly or fail to start.'
  if [ ! -f "$INSTALL_DIR/.spaceworks-version" ]; then
    for port in 80 443; do
      if { command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$port\$"; } \
        || { command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; }; then
        warn "Port $port is already in use; web access on it will not work until it is free."
      fi
    done
  fi
  say "Linux/macOS ($HOST), $(uname -m), ${free_kb} KB free. Log: ${LOG_FILE:-none}"

  step 'Finding the release'
  if [ -z "$VERSION_ARG" ]; then
    where=$(curl -fsS --proto '=https' -o /dev/null -w '%{redirect_url}' "$BASE/$REPO/releases/latest") \
      || fail "Could not reach $BASE. Check the network connection."
    TAG=${where##*/tag/}
  else
    case $VERSION_ARG in
      *-main.*) TAG=v$VERSION_ARG ;;
      *) TAG=$(curl -fsSL --proto '=https' "$API/repos/$REPO/releases?per_page=100" \
           | grep -o "\"tag_name\": *\"v$VERSION_ARG-main\\.[0-9]*\\.[0-9a-f]*\"" | head -n 1 | sed 's/.*"\(v[^"]*\)"$/\1/') ;;
    esac
  fi
  printf '%s' "$TAG" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}$' \
    || fail "No published release was found${VERSION_ARG:+ for version $VERSION_ARG} in $REPO."
  VER=${TAG#v}; DL="$BASE/$REPO/releases/download/$TAG"; TARBALL="spaceworks-$VER.tar.gz"
  say "Release $VER ($REPO)"
  # Upgrades are forward-only (decision 219g): refuse an older release before downloading anything.
  if [ -f "$INSTALL_DIR/.spaceworks-version" ]; then
    have=$(tr -d '[:space:]' < "$INSTALL_DIR/.spaceworks-version")
    vkey() { printf '%s' "$1" | awk -F'[.-]' '{ printf "%06d%06d%06d%09d", $1, $2, $3, ($4 == "main" ? $5 : 0) }'; }
    cut=18; case $have in *-main.*) cut=27 ;; esac
    if awk -v a="$(vkey "$have" | cut -c1-$cut)" -v b="$(vkey "$VER" | cut -c1-$cut)" 'BEGIN { exit !(b < a) }'; then
      fail "Refusing $VER: $have is installed and upgrades are forward-only. To go back, restore the pre-upgrade backup in $INSTALL_DIR/backups. Nothing was changed."
    fi
  fi
  if [ "$DRY" = 1 ]; then say 'Dry run: nothing will be installed or started.'; fi

  step 'Downloading the release bundle'
  STAGE=$(mktemp -d "${TMPDIR:-/tmp}/.spaceworks-stage.XXXXXX"); trap cleanup EXIT INT TERM
  fetch() { curl -fsSL --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 15 -o "$STAGE/$1" "$DL/$1" \
    || fail "Could not download $1 from $DL."; }
  fetch "$TARBALL"; fetch SHA256SUMS; fetch release.json

  step 'Verifying the download'
  for name in "$TARBALL" release.json; do
    expected=$(awk -v n="$name" '$2 == n || $2 == "*" n {print $1}' "$STAGE/SHA256SUMS")
    printf '%s' "$expected" | grep -Eq '^[0-9a-f]{64}$' || fail "SHA256SUMS has no entry for $name."
    actual=$(cd "$STAGE" && $SHA "$name" | awk '{print $1}')
    [ "$actual" = "$expected" ] || fail "Checksum mismatch for $name; the download is corrupt or was altered. Nothing was installed."
    say "sha256 ok: $name"
  done
  if command -v cosign >/dev/null 2>&1; then
    # Decision 253(d): cosign is present, so a release without signature assets is refused with a clear reason.
    for sig in SHA256SUMS.sig SHA256SUMS.pem; do
      curl -fsSL --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 15 -o "$STAGE/$sig" "$DL/$sig"         || fail 'This release is unsigned or its signature assets are missing (SHA256SUMS.sig / SHA256SUMS.pem), so it cannot be verified. Nothing was installed.'
    done
    identity="^https://github\\.com/$(printf '%s' "$REPO" | sed 's/[.]/\\./g')/\\.github/workflows/release\\.yml@refs/heads/main\$"
    ( cd "$STAGE" && cosign verify-blob --certificate SHA256SUMS.pem --signature SHA256SUMS.sig \
        --certificate-identity-regexp "$identity" \
        --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS >/dev/null 2>&1 ) \
      || fail 'The cosign signature of SHA256SUMS did not verify. Nothing was installed.'
    say 'cosign signature ok (built by this repository'"'"'s release workflow)'
  else
    say 'Only the checksum was verified; install cosign to also verify the release signature.'
  fi

  step 'Unpacking'
  if tar -tzf "$STAGE/$TARBALL" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then fail 'The bundle contains unsafe paths; nothing was installed.'; fi
  mkdir "$STAGE/runtime"; tar -xzf "$STAGE/$TARBALL" -C "$STAGE/runtime" --strip-components=1
  ENTRY="$STAGE/runtime/scripts/installer/install-entry.sh"
  [ -f "$ENTRY" ] || fail "Release $VER predates this installer; use 0.12.0 or newer."
  COMMIT=$(sed -n 's/.*"commit": *"\([0-9a-f]\{40\}\)".*/\1/p' "$STAGE/release.json")
  [ -n "$COMMIT" ] || fail 'release.json carries no commit.'

  step 'Running the installer from the verified bundle'
  SPACEWORKS_STAGED_DIR=$STAGE SPACEWORKS_STAGED_VERSION=$VER SPACEWORKS_STAGED_COMMIT=$COMMIT
  SPACEWORKS_STAGED_SHA256=$(awk -v n="$TARBALL" '$2 == n || $2 == "*" n {print $1}' "$STAGE/SHA256SUMS")
  SPACEWORKS_INSTALL_LOG=$LOG_FILE; SPACEWORKS_REPOSITORY=$REPO
  export SPACEWORKS_STAGED_DIR SPACEWORKS_STAGED_VERSION SPACEWORKS_STAGED_COMMIT SPACEWORKS_STAGED_SHA256 \
    SPACEWORKS_INSTALL_LOG SPACEWORKS_REPOSITORY
  rc=0
  bash "$ENTRY" "$@" < /dev/null || rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '%sThe installer stopped (exit %s).%s Details: %s\n' "$RED" "$rc" "$OFF" "${LOG_FILE:-no log}" >&2
    exit "$rc"
  fi
  if [ "$DRY" = 0 ] && [ -d "$INSTALL_DIR" ] && [ -n "$LOG_FILE" ] && [ "$LOG_FILE" != "$INSTALL_DIR/install.log" ]; then
    cp "$LOG_FILE" "$INSTALL_DIR/install.log" 2>/dev/null || true
  fi
  exit 0
}

main "$@"
