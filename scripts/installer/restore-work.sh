#!/usr/bin/env bash
# Refuse redirected work paths before root writes or removes plaintext.
validate_restore_workspace() {
  local path
  [[ "$OPS_WORK_DIR" == "$OPS_DIR/work" && "$WORK" == "$OPS_WORK_DIR/restore-$RESTORE_ID" \
     && "$BUNDLE" == "$WORK/bundle" ]] || return 1
  for path in "$OPS_WORK_DIR" "$WORK" "$BUNDLE"; do
    [[ ! -L "$path" && ( ! -e "$path" || -d "$path" ) ]] || return 1
  done
  for path in "$ARCHIVE" "$PLAIN" "$JOURNAL" "$PRE_DB" "$CONTROL_RECORD" "$DESTRUCTIVE_MARKER"; do
    [[ ! -L "$path" && ( ! -e "$path" || -f "$path" ) ]] || return 1
  done
}

cleanup_completed_restore_plaintext() {
  [[ "$finished" == 1 ]] || return 1
  validate_restore_workspace || return
  # Completed DB/object validation and cleanup-rollback have already succeeded.
  # Ambiguous/failed operations retain their private rollback material.
  rm -f -- "$PLAIN" "$PRE_DB" "$CONTROL_RECORD" || return
  rm -rf -- "$BUNDLE"
}
