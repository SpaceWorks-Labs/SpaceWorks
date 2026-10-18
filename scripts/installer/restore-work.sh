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
  prove_terminal_restore || return
  # Completed DB/object validation and cleanup-rollback have already succeeded.
  # Ambiguous/failed operations retain their private rollback material.
  rm -f -- "$PLAIN" "$PRE_DB" "$CONTROL_RECORD" || return
  rm -rf -- "$BUNDLE" || return
  seal_terminal_restore_work restored
}

seal_terminal_restore_work() {
  local outcome="$1"
  validate_restore_workspace || return
  prove_terminal_restore || return
  source "$RESTORE_SCRIPT_DIR/installer/retention.sh"
  # Keep receipts above app-writable work/: the runtime UID cannot forge terminal
  # permission to age-delete a root supervisor's pre-restore database snapshot.
  seal_recovery_batch "$RESTORE_SCRIPT_DIR" "$OPS_DIR" "$outcome" "$WORK" || return
  expire_recovery_batches "$RESTORE_SCRIPT_DIR" "$OPS_DIR" "$WORK"
}

prove_terminal_restore() {
  "${COMPOSE[@]}" run --rm --no-deps -T backend --role management python -c \
    "$(cat "$RESTORE_SCRIPT_DIR/installer/restore-terminal.py")" "$RESTORE_ID" >/dev/null
}

retain_rolled_back_restore() {
  control cleanup-rollback "$RESTORE_ID" >/dev/null || return
  prove_terminal_restore || return
  rm -f -- "$DESTRUCTIVE_MARKER" || return
  seal_terminal_restore_work rolled_back
}

reconcile_completed_restore_work() {
  control cleanup-rollback "$RESTORE_ID" >/dev/null || return
  prove_terminal_restore || return
  rm -f -- "$DESTRUCTIVE_MARKER" || return
  finished=1
  cleanup_completed_restore_plaintext
}
