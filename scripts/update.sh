#!/usr/bin/env bash
# Apply the newest fully-published Space Works release to a production Compose stack.
set +x
set -euo pipefail

UPDATE_ARGUMENTS=("$@")
UPDATE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SPACEWORKS_UPDATE_INSTALL_DIR:-$(cd "$UPDATE_SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"
export SPACEWORKS_UPDATE_INSTALL_DIR="$ROOT"
source "$UPDATE_SCRIPT_DIR/install-owner.sh"
require_install_owner "$UPDATE_SCRIPT_DIR/update.sh" "$@"

COMPOSE=("$UPDATE_SCRIPT_DIR/spaceworks-compose.sh" bundled)
# The old wrapper/proofs are still authoritative until backup and bundle replacement.
if [[ "$UPDATE_SCRIPT_DIR" != "$ROOT/scripts" ]]; then
  COMPOSE=("$ROOT/scripts/spaceworks-compose.sh" bundled)
fi
source "$UPDATE_SCRIPT_DIR/compose-deployment.sh"
deployment_services
LOCK_DIR="$ROOT/.spaceworks-update.lock"
VERSION_FILE="$ROOT/.spaceworks-version"
source "$UPDATE_SCRIPT_DIR/spaceworks-repository.sh"
configure_release_repository
source "$UPDATE_SCRIPT_DIR/installer/host-paths.sh"
resolve_host_paths || exit $?
export SPACEWORKS_OPS_HOST_DIR="$OPS_DIR"
RELEASE_API="https://api.github.com/repos/$SPACEWORKS_REPOSITORY/releases?per_page=100"
update_complete=0
deployment_started=0
host_configuration_started=0
previous_version=""
UPDATE_LOCK_HELD=0
UPDATE_LOCK_OVERRIDE=0
MODULE_REQUESTED=0
MODULE_ONLY=0
MODULE_MODE=interactive
MODULE_INTERACTIVE=0
MODULE_MAKERSPACE=""
MODULE_ALL_MAKERSPACES=0
MODULE_WITHOUT=""
MODULE_AREAS=""
MODULE_CONFIRM_REMOVALS=0
NO_MODULE_CHANGES=0
REQUESTED_VERSION=""
BUNDLE_STAGE=""

say() { printf '[Space Works updater] %s\n' "$*"; }
warn() { printf '[Space Works updater] WARNING: %s\n' "$*" >&2; }
die() { printf '[Space Works updater] ERROR: %s\n' "$*" >&2; exit 1; }
source "$UPDATE_SCRIPT_DIR/update-lock.sh"
source "$UPDATE_SCRIPT_DIR/module-selection.sh"
source "$UPDATE_SCRIPT_DIR/cleanup-run-once.sh"
source "$UPDATE_SCRIPT_DIR/update-rollback.sh"
source "$UPDATE_SCRIPT_DIR/install-host-bundle.sh"
source "$UPDATE_SCRIPT_DIR/update-release-bundle.sh"
source "$UPDATE_SCRIPT_DIR/update-proxy-edges.sh"
source "$UPDATE_SCRIPT_DIR/installer/update-backup.sh"
source "$UPDATE_SCRIPT_DIR/installer/key-backfill.sh"

while (($# > 0)); do
  case "$1" in
    --force) ;;
    --version)
      [[ -z "$REQUESTED_VERSION" ]] || die "--version may only be specified once."
      shift; (($# > 0)) || die "--version requires an immutable main release version."
      REQUESTED_VERSION="$1"
      [[ "$REQUESTED_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}$ ]] \
        || die "--version requires X.Y.Z-main.<run>.<12 lowercase hex SHA>."
      ;;
    --modules) MODULE_REQUESTED=1; MODULE_MODE=interactive ;;
    --modules-only) MODULE_REQUESTED=1; MODULE_ONLY=1 ;;
    --no-module-changes) NO_MODULE_CHANGES=1 ;;
    --all-modules) MODULE_REQUESTED=1; MODULE_MODE=all ;;
    --areas=*) MODULE_REQUESTED=1; MODULE_MODE=areas; MODULE_AREAS="${1#*=}" ;;
    --without=*)
      MODULE_REQUESTED=1; MODULE_WITHOUT="${1#*=}"
      [[ "$MODULE_MODE" == all || "$MODULE_MODE" == areas ]] || MODULE_MODE=without
      ;;
    --makerspace)
      shift; (($# > 0)) || die "--makerspace requires a slug."
      MODULE_MAKERSPACE="$1"; MODULE_REQUESTED=1
      ;;
    --all-makerspaces) MODULE_ALL_MAKERSPACES=1; MODULE_REQUESTED=1 ;;
    --confirm-removals) MODULE_CONFIRM_REMOVALS=1 ;;
    --override-lock) UPDATE_LOCK_OVERRIDE=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/update.sh [--force] [--version <version>] [module options]
  --version <version>       deploy this exact published main release of the configured repository
  --modules                 interactively review current areas (on/partial/off)
  --modules-only            change modules without checking for a release
  --all-modules             enable every area and every supported feature in it; existing settings are kept
  --areas=inventory,machines,...  select exactly these areas (empty = core and always-on only)
  --without=key1,key2       keep current state, or all modules, except these keys
  --makerspace <slug>       target one makerspace
  --all-makerspaces         explicitly target every makerspace
  --confirm-removals        acknowledge retained-data module removals non-interactively
  --no-module-changes       update images only
  --override-lock           clear a verified stale/wedged portable update lock
EOF
      exit 0
      ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done
[[ "$MODULE_ALL_MAKERSPACES" == 0 || -z "$MODULE_MAKERSPACE" ]] \
  || die "Use either --makerspace or --all-makerspaces, not both."
[[ "$NO_MODULE_CHANGES" == 0 || "$MODULE_REQUESTED" == 0 ]] \
  || die "--no-module-changes cannot be combined with module-selection options."
[[ "$MODULE_ONLY" == 0 || -z "$REQUESTED_VERSION" ]] \
  || die "--version cannot be combined with --modules-only."
if [[ "$MODULE_REQUESTED" == 0 && "$NO_MODULE_CHANGES" == 0 && -t 0 && -t 1 ]]; then
  MODULE_REQUESTED=1
  MODULE_MODE=interactive
fi
if [[ "$MODULE_MODE" == interactive ]]; then
  [[ "$MODULE_REQUESTED" == 0 || ( -t 0 && -t 1 ) ]] \
    || die "Interactive module selection needs a terminal; use --all-modules/--without or --no-module-changes."
  MODULE_INTERACTIVE="$MODULE_REQUESTED"
fi


command -v docker >/dev/null 2>&1 || die "Docker is not installed."
command -v curl >/dev/null 2>&1 || die "curl is required to check GitHub releases."
cleanup() {
  exit_code=$?
  trap - EXIT
  set +e
  if [[ "$deployment_started" == 1 && "$update_complete" == 0 ]]; then
    rollback_application_images
    [[ "${UPDATE_ROLLBACK_PROVEN:-0}" != 1 ]] || seal_update_backups rolled_back \
      || warn 'Healthy image rollback retained private backups without automatic expiry.'
  fi
  if [[ "$exit_code" != 0 && "$host_configuration_started" == 1 && "$deployment_started" == 0 ]]; then
    warn "Host configuration upgrade stopped before deployment; the database was not replaced."
    if declare -F rollback_host_configuration >/dev/null && rollback_host_configuration; then
      say 'Restored the exact previous host files, environment and topology records; keep the database backup.'
      seal_update_backups rolled_back || warn 'Configuration rollback retained backups without automatic expiry.'
    else
      warn 'Host rollback needs recovery from the private host-config snapshot; keep writers stopped.'
    fi
  fi
  release_update_lock
  if [[ -n "$BUNDLE_STAGE" && "$BUNDLE_STAGE" == "$ROOT"/.spaceworks-update.* ]]; then
    rm -rf -- "$BUNDLE_STAGE"
  fi
  exit "$exit_code"
}
trap cleanup EXIT
SPACEWORKS_LEGACY_LOCK_ONLY=0
if [[ ! -f "$OPS_DIR/database-pointer.env" || ! -f "$ROOT/scripts/spaceworks-compose.sh" ]]; then
  SPACEWORKS_LEGACY_LOCK_ONLY=1
fi
acquire_update_lock
source "$UPDATE_SCRIPT_DIR/installer/pre-h1.sh"
transition_pre_h1
source "$UPDATE_SCRIPT_DIR/retire-update-polling.sh"
retire_update_polling

if [[ "$MODULE_REQUESTED" == 1 ]]; then
  module_targets || die "Module targeting failed; no release or module changes were made."
  if [[ "$MODULE_ALL_MAKERSPACES" == 0 ]]; then
    MODULE_MAKERSPACE="${MODULE_TARGETS[0]}"
  fi
fi
if [[ "$MODULE_ONLY" == 1 ]]; then
  change_modules || die "One or more requested module changes were not applied."
  say "Module review complete."
  exit 0
fi

# A pinned deployment checks its exact tag, including releases beyond the list's first page.
if [[ -n "$REQUESTED_VERSION" ]]; then
  RELEASE_API="https://api.github.com/repos/$SPACEWORKS_REPOSITORY/releases/tags/v$REQUESTED_VERSION"
fi
release_json="$(curl --fail --silent --show-error --location \
  --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 5 \
  --header 'Accept: application/vnd.github+json' \
  --header 'User-Agent: spaceworks-self-host-updater' "$RELEASE_API")"
version="$(printf '%s' "$release_json" | "${COMPOSE[@]}" exec -T "$APP_SERVICE" \
  python -c "$(cat "$UPDATE_SCRIPT_DIR/select-main-release.py")" "$REQUESTED_VERSION" "$SPACEWORKS_REPOSITORY")" \
  || die "Could not validate an eligible published main release. Start the app, then retry."
version="$(printf '%s' "$version" | tr -d '\r\n')"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}$ ]] \
  || die "The updater requires an immutable published main release version."
current=""
[[ ! -f "$VERSION_FILE" ]] || current="$(tr -d '[:space:]' < "$VERSION_FILE")"
previous_version="$current"
if [[ "$current" == "$version" ]]; then
  say "$version is already installed."
  if [[ "$MODULE_REQUESTED" == 1 ]]; then change_modules; fi
  exit 0
fi

refuse_release_downgrade
handoff_release_bundle
say "Updating ${current:-untracked installation} to $version."

create_update_backup
source "$UPDATE_SCRIPT_DIR/installer/privileged-target.sh"
admit_privileged_target "$UPDATE_SCRIPT_DIR" || die 'Cannot prove the privileged migration target; no host configuration was changed.'
export MAKERSPACE_IMAGE_TAG="$version"

# Check the new backend image exists before replacing any committed host configuration.
docker pull "$MAKERSPACE_BACKEND_IMAGE:$version"
plan_key_backfill
host_configuration_started=1
source "$UPDATE_SCRIPT_DIR/retire-update-tombstone.sh"
retire_update_tombstone
install_staged_host_bundle "$(cd "$UPDATE_SCRIPT_DIR/.." && pwd)"
# Keep future runner and manual runs on the same configured repository.
if [[ -f "$ROOT/.env" ]]; then
  repository_file="$(mktemp "$ROOT/.deploy-env.XXXXXX")"
  sed '/^SPACEWORKS_REPOSITORY=/d' "$ROOT/.env" > "$repository_file"
  printf '\nSPACEWORKS_REPOSITORY=%s\n' "$SPACEWORKS_REPOSITORY" >> "$repository_file"
  chmod 600 "$repository_file"
  mv -f -- "$repository_file" "$ROOT/.env"
fi
# Persist resolved host selectors before sealing the new configuration; ambient
# values can never redirect a deployment after this repair.
source "$UPDATE_SCRIPT_DIR/setup-write-environment.sh"
source "$UPDATE_SCRIPT_DIR/installer/environment-continuity.sh"
forward_installer_environment || die 'Could not preserve explicit deployment settings.'
for selector in SPACEWORKS_OPS_HOST_DIR SPACEWORKS_HOST_STATE_DIR; do
  grep -q "^$selector=" "$ROOT/.env" || env_setting "$selector" "${!selector}"
done
# Pin the newly installed wrapper and record its new compose hashes before using it.
# The direct Docker pull above did not depend on the still-old digest records.
HOST_CONFIG_IMAGE="$MAKERSPACE_BACKEND_IMAGE:$version"
OPS_HOST_DIR="$OPS_DIR"
source "$UPDATE_SCRIPT_DIR/setup-host-orchestration.sh"
source "$UPDATE_SCRIPT_DIR/setup-question-input.sh"
source "$UPDATE_SCRIPT_DIR/installer/setup-state.sh"
ensure_station_pepper no-refresh
apply_key_backfill
backfill_absent_continuity_keys || die 'Could not add the missing encryption keys.'
backfill_platform_staff_origin || die 'Could not add the platform sign-in origin.'
refresh_compose_config
COMPOSE=("$UPDATE_SCRIPT_DIR/spaceworks-compose.sh" bundled)
say "Pulling immutable release images."
${COMPOSE[@]+"${COMPOSE[@]}"} pull ${IMAGE_SERVICES[@]+"${IMAGE_SERVICES[@]}"}

# Refresh the producer proof for the new migration tree before any new workers start.
HOST_CONFIG_IMAGE="$MAKERSPACE_BACKEND_IMAGE:$version"
source "$UPDATE_SCRIPT_DIR/setup-host-orchestration.sh"
install_producer_capability
say "Running migrations and replacing application containers."
# Always exclude every local writer before the migrate dependency can start.
# This also covers irreversible data migrations; external writers must be fenced by the operator.
deployment_started=1
"${COMPOSE[@]}" stop backend worker beat live
${COMPOSE[@]+"${COMPOSE[@]}"} up -d --remove-orphans
refresh_update_proxy_edges

wait_for_backend || die "Release $version did not become ready. The backup is backups/$backup_name."
source "$UPDATE_SCRIPT_DIR/installer/completion.sh"
verify_full_host_completion "$UPDATE_SCRIPT_DIR" || die 'Required full-host runtime checks failed.'
# One-off after the 0.12.0 upgrade: recompute every space's managed-storage figure from the canonical rows
# (decision 284 polish). Idempotent; the marker stops it repeating. A failure only warns.
storage_marker="$ROOT/.spaceworks-storage-recomputed-0.12.0"
if [[ ! -e "$storage_marker" ]]; then
  say "Recomputing storage usage for existing spaces (one-off)."
  if "${COMPOSE[@]}" exec -T backend python manage.py recompute_storage; then
    : > "$storage_marker"
  else
    warn "Storage recompute did not finish; run 'python manage.py recompute_storage' in the backend container."
  fi
fi

# Decision 308(c): existing accounts get their username as handle when it is valid and free (idempotent).
handle_marker="$ROOT/.spaceworks-handles-claimed-0.12.0"
if [[ ! -e "$handle_marker" ]]; then
  say "Giving existing accounts their username as profile handle where it is free (one-off)."
  if "${COMPOSE[@]}" exec -T backend python manage.py claim_default_handles; then
    : > "$handle_marker"
  else
    warn "Handle backfill did not finish; run 'python manage.py claim_default_handles' in the backend container."
  fi
fi

if [[ ! -e "$ROOT/.git" ]]; then
  host_bundle_files
  project_name="$("${COMPOSE[@]}" config --format json | python3 "$UPDATE_SCRIPT_DIR/installer/project-name.py")"
  printf '%s\n' "${HOST_BUNDLE_FILES[@]}" | python3 "$UPDATE_SCRIPT_DIR/installer/managed-files.py" \
    "$ROOT" "$(cd "$UPDATE_SCRIPT_DIR/.." && pwd)/.spaceworks-release.json" "$project_name" || die 'Runtime registration failed.'
fi
source "$UPDATE_SCRIPT_DIR/installer/retention-schedule.sh"
configure_retention_maintenance install "$UPDATE_SCRIPT_DIR" || die 'Daily retention maintenance could not be installed; retry the update.'
printf '%s\n' "$version" > "$VERSION_FILE"
update_complete=1
retained_paths=("$ROOT/backups/$backup_name")
[[ -z "${HOST_CONFIG_BACKUP_DIR:-}" ]] || retained_paths+=("$HOST_CONFIG_BACKUP_DIR")
source "$UPDATE_SCRIPT_DIR/installer/retention.sh"
seal_update_backups updated \
  || warn 'Terminal backup receipt failed; recovery files will not expire automatically.'
cleanup_run_once_jobs || warn "Could not remove finished start-up jobs."
expire_recovery_batches "$UPDATE_SCRIPT_DIR" "$ROOT" "${retained_paths[@]}" \
  || warn 'Private backup retention was refused; inspect the retained backups.'
say "Release update complete: $version."
if [[ "$MODULE_REQUESTED" == 1 ]]; then
  change_modules || die "Release $version is healthy, but one or more module changes were not applied."
fi
say "Update complete: $version."
