#!/usr/bin/env bash
# All snapshots finish before replacement starts. Caller holds operation.lock.
bundle_path_safe() {
  local relative="$1" cursor="$ROOT" part
  local parts=(); IFS=/ read -ra parts <<< "$relative"
  [[ "$relative" != /* ]] || return 1
  for part in "${parts[@]}"; do
    [[ -n "$part" && "$part" != . && "$part" != .. ]] || return 1
    cursor+="/$part"
    [[ ! -L "$cursor" ]] || return 1
  done
}

snapshot_host_configuration() {
  local relative destination
  bundle_path_safe backups || return
  for relative in "${HOST_BUNDLE_FILES[@]}" "${RETIRED_HOST_FILES[@]}" .env; do
    bundle_path_safe "$relative" || return
  done
  mkdir -p "$HOST_CONFIG_BACKUP_DIR" || return
  chmod 700 "$HOST_CONFIG_BACKUP_DIR" || return
  : > "$HOST_CONFIG_BACKUP_DIR/files" || return
  for relative in "${HOST_BUNDLE_FILES[@]}" "${RETIRED_HOST_FILES[@]}" .env; do
    destination="$ROOT/$relative"
    if [[ -f "$destination" ]]; then
      mkdir -p "$HOST_CONFIG_BACKUP_DIR/$(dirname "$relative")" || return
      cp -p -- "$destination" "$HOST_CONFIG_BACKUP_DIR/$relative" || return
      printf 'present %s\n' "$relative" >> "$HOST_CONFIG_BACKUP_DIR/files" || return
    else
      printf 'absent %s\n' "$relative" >> "$HOST_CONFIG_BACKUP_DIR/files" || return
    fi
  done
  if [[ -n "${OPS_DIR:-}" && -f "$OPS_DIR/compose-topology.json" ]]; then
    local container
    container="$("${COMPOSE[@]}" ps -q backend)" || return
    HOST_RECORD_SNAPSHOT_IMAGE="$(docker inspect --format '{{.Image}}' "$container")" || return
    [[ "$HOST_RECORD_SNAPSHOT_IMAGE" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
    docker run --rm --user 0:0 --network none --entrypoint python \
      -v "$OPS_DIR:/ops" -v "$HOST_CONFIG_BACKUP_DIR:/snapshot" "$HOST_RECORD_SNAPSHOT_IMAGE" \
      -c "$(cat "$UPDATE_SCRIPT_DIR/installer/record-snapshot.py")" snapshot /ops /snapshot/records.json || return
  fi
  HOST_CONFIG_SNAPSHOT_READY=1
}

rollback_host_configuration() {
  [[ "${HOST_CONFIG_SNAPSHOT_READY:-0}" == 1 ]] || return 0
  local state relative destination temporary
  while read -r state relative; do
    destination="$ROOT/$relative"
    if [[ "$state" == present ]]; then
      temporary="$(mktemp "$(dirname "$destination")/.deploy-recover.XXXXXX")" || return
      cp -p -- "$HOST_CONFIG_BACKUP_DIR/$relative" "$temporary" || return
      mv -f -- "$temporary" "$destination" || return
    else
      rm -f -- "$destination" || return
    fi
  done < "$HOST_CONFIG_BACKUP_DIR/files"
  if [[ -f "$HOST_CONFIG_BACKUP_DIR/records.json" ]]; then
    docker run --rm --user 0:0 --network none --entrypoint python \
      -v "$OPS_DIR:/ops" -v "$HOST_CONFIG_BACKUP_DIR:/snapshot" "$HOST_RECORD_SNAPSHOT_IMAGE" \
      -c "$(cat "$UPDATE_SCRIPT_DIR/installer/record-snapshot.py")" restore /ops /snapshot/records.json || return
  fi
  HOST_CONFIG_SNAPSHOT_READY=0
}

apply_host_bundle() {
  local source_root="$1" relative destination temporary
  for relative in "${HOST_BUNDLE_FILES[@]}"; do
    destination="$ROOT/$relative"
    mkdir -p "$(dirname "$destination")" || return
    temporary="$(mktemp "$(dirname "$destination")/.deploy-bundle.XXXXXX")" || return
    if ! cp -p -- "$source_root/$relative" "$temporary" || ! mv -f -- "$temporary" "$destination"; then
      rm -f -- "$temporary"
      return 1
    fi
  done
  for relative in "${RETIRED_HOST_FILES[@]}"; do
    rm -f -- "$ROOT/$relative" || return
  done
}
