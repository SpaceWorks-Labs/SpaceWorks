#!/usr/bin/env bash
# Daily host maintenance entrypoint; serializes with every backup/update/restore.
# The installer registers a systemd timer; other hosts schedule this exact command.
set +x
set -euo pipefail
ROOT="${SPACEWORKS_UPDATE_INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT"
source "$ROOT/scripts/installer/restore-owner.sh"
require_restore_root "$ROOT/scripts/installer/retention-run.sh" "$@"
source "$ROOT/scripts/installer/host-paths.sh"
resolve_host_paths
COMPOSE=("$ROOT/scripts/spaceworks-compose.sh" bundled)
source "$ROOT/scripts/compose-deployment.sh"
deployment_services
exec 9>"$OPS_DIR/operation.lock"
flock -n 9 || exit 0
for marker in .spaceworks-import-pending.json .spaceworks-transition.json; do
  [[ ! -e "$ROOT/$marker" && ! -L "$ROOT/$marker" ]] || exit 0
done
source "$ROOT/scripts/installer/retention.sh"
expire_recovery_batches "$ROOT/scripts" "$ROOT"
expire_recovery_batches "$ROOT/scripts" "$OPS_DIR"
