#!/usr/bin/env bash
# Append explicitly supplied settings only. The installed dotenv remains authoritative.
# Never invent account/event key material or replace an existing (even empty) value.
installer_environment_names() {
  local names=(
    ACCOUNT_SAVED_DETAILS_ENABLED ACCOUNT_PII_KEY_BROKER ACCOUNT_PII_MASTER_KEY
    ACCOUNT_PII_MASTER_KEY_PREVIOUS ACCOUNT_PII_AWS_KMS_KEY_ID
    ACCOUNT_SAVED_ASSET_BUDGET_BYTES ACCOUNT_SAVED_RESUME_SCAN_REQUIRED ACCOUNT_SAVED_RESUME_SCANNER
    EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION EVENT_REGISTRATION_CREDENTIAL_KEYS
    EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY
    SPACEWORKS_DEPLOYMENT_MODE SPACEWORKS_DEPLOYMENT_PROFILE SPACEWORKS_DEPLOYMENT_ID
    DATABASE_CONNECTION_MODE DATABASE_MAINTENANCE_CONNECTION_MODE MANAGED_POSTGRES
    CLOUD_SCRATCH_DATABASES_FILE CLOUD_TASK_PROFILE CLOUD_SCHEDULER CRON_INTERVAL_SECONDS
    CELERY_BROKER_URL CELERY_RESULT_BACKEND CELERY_TASK_ALWAYS_EAGER CACHE_URL LIVE_REDIS_URL
    CONN_MAX_AGE CONN_HEALTH_CHECKS DISABLE_SERVER_SIDE_CURSORS
    STORAGE_PRESIGN_METHOD STORAGE_CAPABILITIES_FILE STORAGE_CAPABILITY_TTL_SECONDS
    AWS_SESSION_TOKEN EMAIL_PROVIDER EMAIL_PROVIDER_CONFIG_FILE EMAIL_PROVIDER_WEBHOOKS_ENABLED
    EMAIL_BACKEND DEFAULT_FROM_EMAIL EMAIL_HOST EMAIL_PORT EMAIL_HOST_USER EMAIL_HOST_PASSWORD
    EMAIL_USE_TLS EMAIL_USE_SSL EMAIL_TIMEOUT
    FREE_TICK_INGRESS_LIMIT_PER_MINUTE FREE_MAX_PROMOTION_BYTES
    TRUST_FORWARDED_HOST TRUSTED_EDGE_CIDRS TRUSTED_EDGE_UPSTREAM_HOSTS TRUSTED_EDGE_INGRESS_SECRET
    FREE_TICK_SECRET FREE_TICK_INTERVAL_SECONDS FREE_TICK_BUDGET_SECONDS FREE_TICK_RATE_LIMIT_PER_MINUTE
    FREE_DB_CAP_BYTES FREE_OBJECT_CAP_BYTES FREE_EMAIL_DAILY_CAP FREE_EMAIL_MONTHLY_CAP
    FREE_EMAIL_ACCOUNT_KEY FREE_EMAIL_PROVIDER FREE_EMAIL_ACCOUNTS FREE_EMAIL_RESET_TIMEZONE
    SPACEWORKS_INSTALLER_TEST_EMAIL SPACEWORKS_INSTALLER_REQUIRED_PROBES
  )
  printf '%s\n' "${names[@]}"
}

preserve_installer_environment() {
  local name result=''
  while IFS= read -r name; do
    [[ -v "$name" ]] || continue
    export "$name"
    result+="${result:+,}$name"
  done < <(installer_environment_names)
  INSTALLER_PRESERVED_NAMES="$result"
}

forward_installer_environment() {
  local name value
  [[ -f "$ROOT/.env" && ! -L "$ROOT/.env" ]] || return 1
  [[ "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" == full ]] || {
    echo 'VPS installer accepts the full profile only.' >&2; return 1;
  }
  [[ "$(deployment_value SPACEWORKS_DEPLOYMENT_PROFILE)" != free ]] || return 1
  while IFS= read -r name; do
    grep -q "^$name=" "$ROOT/.env" && continue
    [[ -v "$name" ]] || continue
    value="${!name}"
    [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || {
      echo 'Installer setting contains a forbidden line break; environment retained.' >&2; return 1;
    }
    env_setting "$name" "$value" "$ROOT/.env" || return
  done < <(installer_environment_names)
  # Compose gives exported shell values precedence over --env-file. Clearing the
  # allowlist prevents an ambient key from overriding the retained installed key.
  while IFS= read -r name; do unset "$name"; done < <(installer_environment_names)
  chmod 600 "$ROOT/.env"
}
