#!/usr/bin/env bash
# Import a downloaded full-deployment archive, record intent, then run disaster restore.
set +x
set -euo pipefail
umask 077

ROOT="${SPACEWORKS_UPDATE_INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"
source "$ROOT/scripts/installer/restore-owner.sh"
require_restore_root "$ROOT/scripts/import-backup.sh" "$@"
COMPOSE=("$ROOT/scripts/spaceworks-compose.sh" bundled)
source "$ROOT/scripts/installer/host-paths.sh"
resolve_host_paths || exit $?
source "$ROOT/scripts/compose-deployment.sh"
deployment_services
source "$ROOT/scripts/installer/import-environment.sh"
OPS_WORK_DIR="$OPS_DIR/work"
IDENTITY_FILE="${BACKUP_AGE_IDENTITY_FILE:-$OPS_WORK_DIR/age-identity.txt}"
SOURCE="${1:-}"
USERNAME="${2:-}"
EXPECTED_SHA256="${3:-}"

die() { printf '[Space Works backup import] ERROR: %s\n' "$*" >&2; exit 1; }
if [[ "$SOURCE" != --recover-environment ]]; then
  [[ -f "$SOURCE" && -n "$USERNAME" ]] \
    || die "Usage: scripts/import-backup.sh <archive.tar.age> <target-superadmin-username> [expected-sha256] (or --recover-environment)"
  [[ -f "$IDENTITY_FILE" ]] || die 'The age identity is missing.'
fi
[[ -d "$OPS_DIR" && ! -L "$OPS_WORK_DIR" ]] || die 'The operation directory is missing or redirected.'
command -v flock >/dev/null 2>&1 || die "flock is required."
[[ "$(uname -s)" == Linux ]] || die 'Backup import/restore requires Linux or WSL2.'

exec 9>"$OPS_DIR/operation.lock"
flock -n 9 || die "Another backup, restore, verification, or update is running."
if [[ "$SOURCE" == --recover-environment ]]; then
  recover_import_environment || die 'Interrupted continuity installation requires private recovery.'
  exit 0
fi
[[ ! -e "$ROOT/.spaceworks-import-pending.json" && ! -L "$ROOT/.spaceworks-import-pending.json" ]] \
  || die 'Recover the interrupted environment first with scripts/import-backup.sh --recover-environment, then retry the signed archive.'
source "$ROOT/scripts/installer/capacity.sh"
require_operation_capacity import "$SOURCE" || die 'Insufficient measured import capacity; no archive copied.'
WORK="$(mktemp -d "$OPS_WORK_DIR/import-XXXXXXXX")"
if [[ "$(id -u)" == "0" ]]; then
  chown -R 10001:10001 "$WORK"
fi
CONTAINER_WORK="${WORK/$OPS_WORK_DIR/\/var\/lib\/spaceworks\/ops\/work}"
cleanup() {
  local status=$?
  trap - EXIT
  if ! rollback_import_environment; then
    echo "Import recovery requires the private state in $WORK; writers remain stopped." >&2
    exit 1
  fi
  rm -rf -- "$WORK"
  exit "$status"
}
trap cleanup EXIT
cp -- "$SOURCE" "$WORK/archive.tar.age"
if [[ "$(id -u)" == "0" ]]; then
  chown 10001:10001 "$WORK/archive.tar.age"
fi

"${COMPOSE[@]}" exec -T backend age -d \
  -i "${IDENTITY_FILE/$OPS_DIR/\/var\/lib\/spaceworks\/ops}" \
  -o "$CONTAINER_WORK/archive.tar" "$CONTAINER_WORK/archive.tar.age"
require_operation_capacity import "$WORK/archive.tar.age" "$WORK/archive.tar" \
  || die 'Insufficient measured archive extraction capacity.'
"${COMPOSE[@]}" exec -T backend python - \
  "$CONTAINER_WORK/archive.tar" "$CONTAINER_WORK/manifest.json" \
  "$CONTAINER_WORK/keys-env.json" <<'PY'
import pathlib
import sys
import tarfile

archive, manifest_output, keys_output = map(pathlib.Path, sys.argv[1:])
with tarfile.open(archive) as bundle:
    members = {member.name.lstrip("./"): member for member in bundle.getmembers()}
    for name, output in (("manifest.json", manifest_output), ("keys/env.json", keys_output)):
        member = members.get(name)
        if member is None or not member.isfile():
            raise SystemExit(f"The archive has no regular {name} member.")
        source = bundle.extractfile(member)
        if source is None:
            raise SystemExit(f"The archive member {name} cannot be read.")
        output.write_bytes(source.read())
PY

preflight_args=(
  --encrypted-file "$CONTAINER_WORK/archive.tar.age"
  --bundle "$CONTAINER_WORK/archive.tar"
  --manifest "$CONTAINER_WORK/manifest.json"
  --continuity-secrets "$CONTAINER_WORK/keys-env.json"
)
if [[ -n "$EXPECTED_SHA256" ]]; then
  preflight_args+=(--expected-sha256 "$EXPECTED_SHA256")
fi
"${COMPOSE[@]}" run --rm --no-deps -T backend \
  --role management python manage.py preflight_backup_import "${preflight_args[@]}"

[[ -f .env ]] || die "The target deployment has no .env file to receive continuity secrets."
cp -p -- .env "$WORK/target.env"
if [[ "$(id -u)" == "0" ]]; then
  chown 10001:10001 "$WORK/target.env"
fi
"${COMPOSE[@]}" exec -T backend python - \
  "$CONTAINER_WORK/target.env" "$CONTAINER_WORK/keys-env.json" <<'PY'
import json
import os
from pathlib import Path
import re
import sys

target, source = map(Path, sys.argv[1:])
try:
    from apps.backup.continuity import validate_continuity_secrets
except ImportError:
    raise SystemExit("The matching release continuity schema is unavailable; import refused.") from None
values = json.loads(source.read_text(encoding="utf-8"))
try:
    values = validate_continuity_secrets(values)
except (ValueError, TypeError):
    raise SystemExit("Archive continuity is incompatible. Recover the original station pepper and matching keys; never generate replacement archive keys.") from None
if any(not isinstance(value, str) or "\n" in value or "\r" in value for value in values.values()):
    raise SystemExit("A continuity secret cannot be represented safely in the Compose environment.")
lines = target.read_text(encoding="utf-8").splitlines()
remaining = dict(values)
seen = set()
for index, line in enumerate(lines):
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
    if match and match.group(1) in remaining:
        name = match.group(1)
        value = remaining.pop(name).replace("\\", "\\\\").replace("'", "\\'")
        lines[index] = f"{name}='{value}'"
        seen.add(name)
    elif match and match.group(1) in seen:
        raise SystemExit("The target environment repeats a continuity key; import refused.")
for name, raw in sorted(remaining.items()):
    value = raw.replace("\\", "\\\\").replace("'", "\\'")
    lines.append(f"{name}='{value}'")
temporary = target.with_suffix(".new")
descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines) + "\n")
    handle.flush()
    os.fsync(handle.fileno())
temporary.replace(target)
PY
install_import_environment || die 'Continuity installation failed; restoring the previous environment and topology.'
printf '[Space Works backup import] Continuity installed; private recovery environment: %s.\n' "$env_backup"

import_args=(
  --username "$USERNAME"
  --encrypted-file "$CONTAINER_WORK/archive.tar.age"
  --bundle "$CONTAINER_WORK/archive.tar"
  --manifest "$CONTAINER_WORK/manifest.json"
  --continuity-secrets "$CONTAINER_WORK/keys-env.json"
)
if [[ -n "$EXPECTED_SHA256" ]]; then
  import_args+=(--expected-sha256 "$EXPECTED_SHA256")
fi
# No writer may continue on a possibly mixed DB/key generation after registration.
"${COMPOSE[@]}" stop "$APP_SERVICE" "${WORKER_SERVICES[@]}"
python3 "$ROOT/scripts/installer/import-journal.py" seal "$ROOT" "$OPS_DIR"
import_env_ambiguous=1
registration_output="$(mktemp "$ROOT/.spaceworks-import-result.XXXXXX")"
if ! "${COMPOSE[@]}" run --rm --no-deps -T backend --role management python manage.py import_backup_archive \
  "${import_args[@]}" > "$registration_output" 2>&1; then
  die "Restore registration failed. Private diagnostic file: $registration_output. Keep writers stopped and inspect the retained recovery journals."
fi
restore_id="$(tail -n 1 "$registration_output" | tr -d '\r')"
[[ "$restore_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] || die "The app did not record a restore intent."
python3 "$ROOT/scripts/installer/import-journal.py" registered "$ROOT" "$OPS_DIR" "$restore_id"
rm -f -- "$registration_output"
flock -u 9
exec 9>&-
bash "$ROOT/scripts/restore.sh" "$restore_id"
exec 9>"$OPS_DIR/operation.lock"
flock -n 9 || die 'Another operation started before import completion; retain the private continuity journal.'
"${COMPOSE[@]}" run --rm --no-deps -T backend --role management python -c \
  "$(cat "$ROOT/scripts/installer/restore-terminal.py")" "$restore_id" >/dev/null \
  || die 'Terminal restore completion could not be proven; retain the sealed import journal.'
python3 "$ROOT/scripts/installer/import-journal.py" clear "$ROOT" "$OPS_DIR"
import_env_applied=0
source "$ROOT/scripts/installer/retention.sh"
seal_recovery_batch "$ROOT/scripts" "$ROOT" restored "$ROOT/$env_backup" \
  || echo 'Environment backup retained without automatic expiry: terminal receipt could not be sealed.' >&2
expire_recovery_batches "$ROOT/scripts" "$ROOT" "$ROOT/$env_backup"
trap - EXIT
rm -rf -- "$WORK"
