#!/usr/bin/env bash
# Root-only topology snapshots remain 0600. Use pinned offline tooling to read them;
# do not make snapshots group-readable just to let the unprivileged updater prune.
private_retention_tool() {
  local directory="$1" root="$2" tool="$3" image container
  shift 3
  [[ "$root" == "$ROOT" || "$root" == "$OPS_DIR" ]] || return 1
  [[ -d "$root" && ! -L "$root" ]] || return 1
  container="$("${COMPOSE[@]}" ps -a -q "$APP_SERVICE")" || return
  image="$(docker inspect --format '{{.Image}}' "$container")" || return
  [[ "$image" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  docker run --rm --user 0:0 --network none --entrypoint python \
    -v "$root:/retention-root" -v "$directory/installer:/retention-tools:ro" \
    "$image" "/retention-tools/$tool" "$@"
}

seal_recovery_batch() {
  local directory="$1" root="$2" outcome="$3" path
  shift 3
  local paths=()
  for path in "$@"; do
    [[ "$path" == "$root/"* ]] || return 1
    paths+=("/retention-root/${path#"$root/"}")
  done
  private_retention_tool "$directory" "$root" retention-receipts.py /retention-root "$outcome" "${paths[@]}"
}

expire_recovery_batches() {
  local directory="$1" root="$2" path
  shift 2
  local excludes=()
  for path in "$@"; do
    [[ "$path" == "$root/"* ]] || return 1
    excludes+=(--exclude "/retention-root/${path#"$root/"}")
  done
  private_retention_tool "$directory" "$root" retention.py --root /retention-root "${excludes[@]}"
}
