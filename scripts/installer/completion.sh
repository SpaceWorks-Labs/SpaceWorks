#!/usr/bin/env bash
# Inspect state only: docker inspect/config contain secrets and are never printed.
verify_full_host_completion() {
  local directory="$1" service container state code
  local services=(backend live worker beat)
  # Cron mode has no worker; beat is the scheduler loop.
  [[ "$(deployment_value SPACEWORKS_REDIS)" != none ]] || services=(backend live beat)
  for service in "${services[@]}"; do
    container="$("${COMPOSE[@]}" ps -q "$service")" || return
    [[ -n "$container" && "$container" != *$'\n'* ]] || return 1
    state="$(docker inspect --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")" || return
    [[ "$state" == running\|healthy || "$state" == running\|none ]] || {
      echo 'A required full-host service is stopped or unhealthy; installation is incomplete.' >&2; return 1;
    }
  done
  code="$(python3 "$directory/installer/probe-bundle.py")" || return
  local SPACEWORKS_INSTALLER_TEST_EMAIL SPACEWORKS_INSTALLER_REQUIRED_PROBES
  SPACEWORKS_INSTALLER_TEST_EMAIL="$(deployment_value SPACEWORKS_INSTALLER_TEST_EMAIL)" || return
  SPACEWORKS_INSTALLER_REQUIRED_PROBES="$(deployment_value SPACEWORKS_INSTALLER_REQUIRED_PROBES)" || return
  export SPACEWORKS_INSTALLER_TEST_EMAIL SPACEWORKS_INSTALLER_REQUIRED_PROBES
  printf '%s\n' "$code" | "${COMPOSE[@]}" run --rm --no-deps -T \
    -e SPACEWORKS_INSTALLER_TEST_EMAIL -e SPACEWORKS_INSTALLER_REQUIRED_PROBES backend --role management python -
}
