#!/usr/bin/env bash
# Standalone bootstrap; verify all fetched tooling before executing it.
set +x
set -euo pipefail
(( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4) )) || {
  echo 'SpaceWorks requires Bash 4.4+; macOS needs modern Bash and Docker Desktop.' >&2; exit 64;
}
REPO_ARG=''; ANSWERS_ARG=''; INSTALL_RESUME=0; SETUP_NON_INTERACTIVE=0; PROFILE_ARG=''
ALLOW_PYTHON_BOOTSTRAP=0
while (($#)); do
  case "$1" in
    --repo|--answers-file)
      (($# > 1)) || { echo "Missing value for $1." >&2; exit 64; }
      if [[ "$1" == --repo ]]; then REPO_ARG="$2"; else ANSWERS_ARG="$2"; fi
      shift ;;
    --repo=*) REPO_ARG="${1#*=}" ;;
    --profile) (($# > 1)) || { echo "Missing value for $1." >&2; exit 64; }; PROFILE_ARG="$2"; shift ;;
    --profile=*) PROFILE_ARG="${1#*=}" ;;
    --non-interactive) SETUP_NON_INTERACTIVE=1 ;;
    --resume) INSTALL_RESUME=1 ;;
    --bootstrap-python) ALLOW_PYTHON_BOOTSTRAP=1 ;;
    -h|--help)
      echo 'SpaceWorks full-server installer: install.sh [--repo owner/name] [--resume] [--non-interactive --answers-file private.json]'
      echo 'Ubuntu 24.04 amd64/arm64 is the acceptance target. Linux needs root/sudo; macOS/Windows Git Bash need running Docker Desktop.'
      echo 'Answers: {"schema_version":1,"confirmed":true,"answers":{"ORG_NAME":"My Organization","ADMINEMAIL":"owner@example.org"}}'
      echo 'Optional answers use questionnaire variable names; AREA_ENABLE_inventory etc. select areas. Keep the file mode 0600.'
      echo 'Requires CA certificates and Python 3.10+. Missing Python on Linux is installed only after separate confirmation.'
      echo '--bootstrap-python explicitly permits Python package installation before answers are validated (for minimal noninteractive Linux hosts).'
      echo '--profile free (or SPACEWORKS_DEPLOYMENT_PROFILE=free) opts in to the free single-process profile; full is the default.'
      exit 0 ;;
    *) echo 'Unknown installer option; see install.sh --help.' >&2; exit 64 ;;
  esac
  shift
done
[[ -z "$PROFILE_ARG" ]] || SPACEWORKS_DEPLOYMENT_PROFILE="$PROFILE_ARG"
case "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" in
  full) ;;
  free) export SPACEWORKS_DEPLOYMENT_PROFILE ;;
  *) echo 'Use --profile full (default) or --profile free.' >&2; exit 64 ;;
esac
if [[ "$SETUP_NON_INTERACTIVE" == 1 && -z "$ANSWERS_ARG" && "$INSTALL_RESUME" != 1       && "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" != free ]]; then
  echo '--non-interactive requires --answers-file.' >&2; exit 64
fi
[[ -z "$ANSWERS_ARG" || "$SETUP_NON_INTERACTIVE" == 1 ]] || { echo '--answers-file requires --non-interactive.' >&2; exit 64; }
[[ -z "$ANSWERS_ARG" || "$ANSWERS_ARG" == /* ]] || ANSWERS_ARG="$PWD/$ANSWERS_ARG"
REPOSITORY="${REPO_ARG:-${SPACEWORKS_REPOSITORY:-SpaceWorks-HQ/SpaceWorks}}"
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
if [[ -d "$INSTALL_DIR" && "$(uname -s)" == Linux ]]; then
  owner="$(stat -c %u "$INSTALL_DIR")"
  [[ "$owner" == 0 || "$owner" == "$(id -u)" ]] || { echo 'Run the installer as the existing installation owner.' >&2; exit 64; }
fi
if [[ -z "$REPO_ARG" && -z "${SPACEWORKS_REPOSITORY:-}" && -f "$INSTALL_DIR/.env" ]]; then
  saved="$(sed -n 's/^SPACEWORKS_REPOSITORY=//p' "$INSTALL_DIR/.env" | tr -d '\r')"
  saved="${saved#\'}"; saved="${saved%\'}"; saved="${saved#\"}"; saved="${saved%\"}"
  REPOSITORY="${saved:-$REPOSITORY}"
fi
[[ "$REPOSITORY" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}$ \
   && "$REPOSITORY" != */. && "$REPOSITORY" != */.. ]] || { echo 'Invalid GitHub owner/repository.' >&2; exit 64; }
export SPACEWORKS_REPOSITORY="$REPOSITORY" SPACEWORKS_INSTALL_REPOSITORY_PINNED=1
# Local maintenance remains available without a release-provider connection.
INSTALL_MENU_CHOICE=''
if [[ "$SETUP_NON_INTERACTIVE" == 0 && "$INSTALL_RESUME" == 0 && -f "$INSTALL_DIR/.spaceworks-version" ]]; then
  printf 'Existing SpaceWorks install: 1) Update  2) Change modules  3) Both  4) Cancel  5) Runner  6) Control plane\nChoose 1-6 [4]: ' >&2
  menu_input=/dev/tty
  [[ "${SPACEWORKS_INSTALL_TEST_MODE:-}" != 1 ]] || menu_input="${SPACEWORKS_INSTALL_TEST_TTY:-/dev/tty}"
  IFS= read -r INSTALL_MENU_CHOICE < "$menu_input" || exit 1
  INSTALL_MENU_CHOICE="${INSTALL_MENU_CHOICE:-4}"
  case "$INSTALL_MENU_CHOICE" in
    1|3) ;;
    2) (cd "$INSTALL_DIR" && SPACEWORKS_UPDATE_INSTALL_DIR="$INSTALL_DIR" bash scripts/update.sh --modules-only); exit $? ;;
    5) (cd "$INSTALL_DIR" && bash scripts/install-runner.sh); exit $? ;;
    6) (cd "$INSTALL_DIR" && bash scripts/control-plane-settings.sh); exit $? ;;
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
  [[ "$(uname -s)" == Linux ]] || {
    echo 'Install Python 3.10+ and rerun; no installation state changed.' >&2; exit 64;
  }
  if [[ "$ALLOW_PYTHON_BOOTSTRAP" != 1 ]]; then
    [[ "$SETUP_NON_INTERACTIVE" != 1 ]] || { echo 'Preinstall Python 3.10+ or explicitly pass --bootstrap-python.' >&2; exit 64; }
    printf 'Install Python 3 to verify the release? [y/N]: ' >/dev/tty
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
[[ "${TMPDIR:-/tmp}" != *"'"* && "${TMPDIR:-/tmp}" != *$'\n'* ]] || { echo 'Unsafe temporary-directory name.' >&2; exit 64; }
BOOTSTRAP_STAGE="$(mktemp -d "${TMPDIR:-/tmp}/.spaceworks-stage.XXXXXX")"
trap 'rm -rf -- "$BOOTSTRAP_STAGE"' EXIT
# GitHub TLS is the trust root; bind the verifier to the selected commit's Git blob.
python3 -I - "$REPOSITORY" "$BOOTSTRAP_STAGE" "$INSTALL_DIR" "$INSTALL_RESUME" <<'PY'
import hashlib, json, os, pathlib, re, subprocess, sys
from urllib.parse import urlsplit
repo, stage, install, resume = sys.argv[1:]
stage = pathlib.Path(stage)
def get(url):
    protocols = "=https"
    fixture = os.environ.get("SPACEWORKS_INSTALL_TEST_API", "")
    if fixture:
        parsed = urlsplit(fixture)
        if (os.environ.get("SPACEWORKS_INSTALL_TEST_MODE") != "1" or parsed.hostname != "127.0.0.1"
                or parsed.scheme not in {"http", "https"} or not parsed.port or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("Unsafe test provider override")
        for prefix, replacement in (("https://api.github.com/", "/api/"), ("https://raw.githubusercontent.com/", "/raw/")):
            if url.startswith(prefix):
                url = fixture.rstrip("/") + replacement + url[len(prefix):]
                break
        protocols = "=http,https"
    elif os.environ.get("SPACEWORKS_INSTALL_TEST_MODE"):
        raise ValueError("Missing test provider")
    result = subprocess.run(["curl", "--fail", "--silent", "--location", "--proto", protocols,
        "--proto-redir", protocols, "--connect-timeout", "10", "--max-time", "30", "--retry", "2",
        "--max-filesize", "8000000", "--header", "User-Agent: SpaceWorks-bootstrap", url],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=150, check=False)
    if result.returncode or len(result.stdout) > 8_000_000:
        raise ValueError("Release provider unavailable or oversized")
    return result.stdout

try:
    base = f"https://api.github.com/repos/{repo}"
    pattern = r"v[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}"
    if resume == "1":
        marker = pathlib.Path(install) / ".spaceworks-install.json"
        if marker.is_symlink() or not marker.is_file():
            raise ValueError("Missing resume journal")
        tag = "v" + json.loads(marker.read_text())["release"]
        releases = [json.loads(get(base + f"/releases/tags/{tag}"))]
    else:
        releases = json.loads(get(base + "/releases?per_page=100"))
    eligible = [r for r in releases if isinstance(r, dict) and r.get("draft") is False
                and r.get("prerelease") is False and isinstance(r.get("published_at"), str)
                and r["published_at"] and re.fullmatch(pattern, r.get("tag_name", ""))
                and r.get("html_url", "").lower() == f'https://github.com/{repo}/releases/tag/{r["tag_name"]}'.lower()]
    release = max(eligible, key=lambda r: (r["published_at"], r["tag_name"]))
    version = release["tag_name"][1:]
    commit = json.loads(get(base + f"/commits/v{version}"))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not commit.startswith(version.rsplit(".", 1)[1]):
        raise ValueError("Commit suffix differs")
    tree = json.loads(get(base + f"/git/trees/{commit}?recursive=1"))
    if tree.get("truncated") is not False:
        raise ValueError("Incomplete tree")
    entries = {e["path"]: e for e in tree["tree"]}
    for name in ("scripts/installer/release-fetch.py", "scripts/select-main-release.py"):
        entry = entries[name]
        raw = get(f"https://raw.githubusercontent.com/{repo}/{commit}/{name}")
        if entry["mode"] not in {"100644", "100755"} or hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != entry["sha"]:
            raise ValueError("Verifier checksum mismatch")
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (stage / "version").write_text(version)
except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
    sys.exit("Release bootstrap verification failed; no installation files changed.")
PY
VERSION="$(cat "$BOOTSTRAP_STAGE/version")"
python3 -I "$BOOTSTRAP_STAGE/scripts/installer/release-fetch.py" --repository "$REPOSITORY" \
  --version "$VERSION" --destination "$BOOTSTRAP_STAGE/bundle" >/dev/null
STAGE_DIR="$BOOTSTRAP_STAGE/bundle/runtime"; ARCHIVE=''
die() { echo "[SpaceWorks installer] $*" >&2; exit 1; }
source "$STAGE_DIR/scripts/install-host-bundle.sh"
validate_host_bundle "$STAGE_DIR"
source "$STAGE_DIR/scripts/installer/install-runtime.sh"
