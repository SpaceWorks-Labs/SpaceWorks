#!/usr/bin/env bash
# Retained-data removal. External buckets/offsite copies are never touched.
set +x
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$ROOT/scripts/install-owner.sh"
require_install_owner "$ROOT/scripts/uninstall.sh" "$@"
die() { echo "[SpaceWorks uninstall] $*" >&2; exit 1; }
say() { echo "[SpaceWorks uninstall] $*"; }
purge=0; confirm=''; remove_runner=0
while (($#)); do
  case "$1" in
    --purge-local-data) purge=1 ;;
    --confirm) (($# > 1)) || exit 64; confirm="$2"; shift ;;
    --remove-runner) remove_runner=1 ;;
    -h|--help)
      echo 'uninstall.sh [--remove-runner] [--purge-local-data --confirm DELETE-LOCAL-DATA:<install-directory-name>]'
      echo 'Default: remove recorded services and unchanged managed files; retain volumes, keys, config, backup/operation state and modified files.'
      echo 'Purge deletes owned Compose local volumes only. External buckets/offsite archives and recovery keys are retained.'
      exit 0 ;;
    *) exit 64 ;;
  esac
  shift
done
[[ -f .spaceworks-version && ! -e .git && ( -f .spaceworks-install.json || -f .spaceworks-managed-files.json ) ]] || die 'A dedicated, recorded release installation is required.'
[[ ! -e .spaceworks-import-pending.json && ! -e .spaceworks-transition.json ]] || die 'An incomplete recovery/transition must be resolved before uninstall.'
[[ "$purge" == 0 || "$confirm" == "DELETE-LOCAL-DATA:$(basename "$ROOT")" ]] || die 'Local data purge needs the exact separate confirmation.'
source "$ROOT/scripts/installer/host-paths.sh"
resolve_host_paths
source "$ROOT/scripts/install-host-bundle.sh"
source "$ROOT/scripts/update-lock.sh"
LOCK_DIR="$ROOT/.spaceworks-update.lock"; UPDATE_LOCK_HELD=0
trap release_update_lock EXIT
acquire_update_lock
COMPOSE=("$ROOT/scripts/spaceworks-compose.sh" bundled)
# The committed wrapper validates env hashes, topology, pointer and file ownership.
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" config --format json | python3 "$ROOT/scripts/installer/uninstall-admission.py" "$ROOT" "$purge"
host_bundle_files
printf '%s\n' "${HOST_BUNDLE_FILES[@]}" | python3 "$ROOT/scripts/installer/uninstall-files.py" "$ROOT" --validate
if [[ "$remove_runner" == 1 ]]; then
  bash "$ROOT/scripts/install-runner.sh" --remove || die 'Runner removal failed; application services were retained.'
fi
args=(down --remove-orphans)
[[ "$purge" == 0 ]] || args+=(--volumes)
"${COMPOSE[@]}" "${args[@]}"
host_bundle_files
printf '%s\n' "${HOST_BUNDLE_FILES[@]}" | python3 "$ROOT/scripts/installer/uninstall-files.py" "$ROOT"
say 'Uninstalled. Private config, keys, backups and recovery journals remain at their recorded locations. External storage was unchanged.'
