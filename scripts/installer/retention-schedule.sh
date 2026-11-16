#!/usr/bin/env bash
configure_retention_maintenance() {
  local action="$1" directory="$2"
  # Container-mode acceptance has no init system. Do not pretend installing a unit
  # there schedules anything; the real Ubuntu VM gate verifies the daily timer.
  if [[ "$(uname -s)" != Linux || ! -d /run/systemd/system ]]; then
    [[ "$action" == remove ]] || echo 'No systemd scheduler: arrange a daily root invocation of scripts/installer/retention-run.sh; operation locking and terminal receipts remain mandatory.' >&2
    return 0
  fi
  if [[ "$(id -u)" == 0 ]]; then
    python3 "$directory/installer/retention-schedule.py" "$action" "$ROOT"
  else
    command -v sudo >/dev/null 2>&1 || return 1
    sudo python3 "$directory/installer/retention-schedule.py" "$action" "$ROOT"
  fi
}
