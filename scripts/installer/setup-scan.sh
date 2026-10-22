#!/usr/bin/env bash
# Shared scanner policy for the audited full-host event/finance intake path.
ask_setup_scanner() {
  SETUP_SCAN_MODE=none; SETUP_CLAMD_HOST=''; SETUP_CLAMD_PORT=3310
  if [[ ",${SETUP_SELECTED_AREAS}," == *,events,* && "$HTTPS_MODE" != 1 ]]; then
    echo 'File scanning: bundled uses private ClamAV; external needs a private scanner or protected tunnel. No public scanner port is opened.'
    question SETUP_SCAN_MODE 'File scanning (bundled/external/none)' bundled choices:bundled,external,none || return
    if [[ "$SETUP_SCAN_MODE" == external ]]; then
      question SETUP_CLAMD_HOST 'Private scanner host' '' host || return
      question SETUP_CLAMD_PORT 'Private scanner port' 3310 integer:1:65535 || return
    fi
  fi
  if [[ "$SETUP_SCAN_MODE" == none ]]; then
    echo 'Malware scanning is disabled. Uploaded files remain unscanned; change this policy before accepting untrusted files if scanning is required.'
  fi
}

write_setup_scanner_environment() {
  local mode="${SETUP_SCAN_MODE:-none}"
  case "$mode" in
    bundled)
      env_setting UPLOAD_SCAN_POLICY clamav
      env_setting CLAMD_HOST clamav
      env_setting CLAMD_PORT 3310
      env_setting COMPOSE_PROFILES clamav
      ;;
    external)
      [[ -n "${SETUP_CLAMD_HOST:-}" ]] || return 64
      env_setting UPLOAD_SCAN_POLICY clamav
      env_setting CLAMD_HOST "$SETUP_CLAMD_HOST"
      env_setting CLAMD_PORT "${SETUP_CLAMD_PORT:-3310}"
      ;;
    none) env_setting UPLOAD_SCAN_POLICY none ;;
    *) return 64 ;;
  esac
}
