#!/usr/bin/env bash
# Test every outside service before anything starts (decision 239). Reads the saved .env, runs
# scripts/installer/probe-external.py inside the backend image and passes credentials through the
# container environment, never argv. Local components are not tested here (the normal start-up
# and completion probes cover them).

outside_check_components() {
  local components=''
  [[ "$(deployment_value SPACEWORKS_DATABASE)" != external ]] || components+='database,'
  [[ "$(deployment_value SPACEWORKS_REDIS)" != external ]] || components+='redis,'
  [[ "$(deployment_value SPACEWORKS_STORAGE)" != external ]] || components+='storage,'
  [[ -z "$(deployment_value EMAIL_HOST)" ]] || components+='email,'
  printf '%s' "${components%,}"
}

# env_setting() escapes backslash and single quote; undo it for values given to the container.
outside_value() { deployment_value "$1" | sed 's/\\\(.\)/\1/g'; }

run_outside_checks() {
  local components image name
  components="$(outside_check_components)"
  [[ -n "$components" ]] || return 0
  source "$ROOT/scripts/installer/host-paths.sh"
  resolve_host_paths || return
  image="${HOST_CONFIG_IMAGE:?}"
  say 'Testing the outside services you chose (nothing is started yet)...'
  if [[ "${SPACEWORKS_HOST_CONFIG_BUILD:-0}" == 1 ]]; then
    docker build -q -t "$image" "$ROOT/backend" >/dev/null || return
  else
    docker pull -q "$image" >/dev/null || return
  fi
  export SW_PROBE_COMPONENTS="$components"
  # A first install must find an empty database; an existing install already owns its tables.
  SW_PROBE_EXPECT_EMPTY=1
  [[ ! -f "$OPS_DIR/database-pointer.env" ]] || SW_PROBE_EXPECT_EMPTY=0
  export SW_PROBE_EXPECT_EMPTY
  SW_PROBE_DB_URL="$(outside_value SPACEWORKS_MAINTENANCE_DATABASE_URL)"
  SW_PROBE_REDIS_URL="$(outside_value CELERY_BROKER_URL)"
  SW_PROBE_S3_ENDPOINT="$(outside_value AWS_S3_ENDPOINT_URL)"
  SW_PROBE_S3_PUBLIC_ENDPOINT="$(outside_value AWS_S3_PUBLIC_ENDPOINT_URL)"
  SW_PROBE_S3_REGION="$(outside_value AWS_S3_REGION_NAME)"
  SW_PROBE_S3_ACCESS="$(outside_value AWS_ACCESS_KEY_ID)"
  SW_PROBE_S3_SECRET="$(outside_value AWS_SECRET_ACCESS_KEY)"
  SW_PROBE_PRIVATE_BUCKET="$(outside_value AWS_STORAGE_BUCKET_NAME)"
  SW_PROBE_IMAGE_BUCKET="$(outside_value PUBLIC_IMAGE_BUCKET)"
  SW_PROBE_IMAGE_BASE_URL="$(outside_value PUBLIC_IMAGE_BASE_URL)"
  SW_PROBE_PRESIGN="$(outside_value STORAGE_PRESIGN_METHOD)"
  SW_PROBE_PROFILE="$([[ "$(outside_value STORAGE_PRESIGN_METHOD)" == post ]] && echo full || echo limited)"
  SW_PROBE_SMTP_HOST="$(outside_value EMAIL_HOST)"
  SW_PROBE_SMTP_PORT="$(outside_value EMAIL_PORT)"
  SW_PROBE_SMTP_USER="$(outside_value EMAIL_HOST_USER)"
  SW_PROBE_SMTP_PASSWORD="$(outside_value EMAIL_HOST_PASSWORD)"
  SW_PROBE_SMTP_FROM="$(outside_value DEFAULT_FROM_EMAIL)"
  SW_PROBE_SMTP_TLS="$([[ "$(outside_value EMAIL_USE_TLS)" == True ]] && echo 1 || echo 0)"
  SW_PROBE_TEST_EMAIL_TO=''
  [[ ! "${SMTP_TEST:-N}" =~ ^[Yy] ]] || SW_PROBE_TEST_EMAIL_TO="${ADMINEMAIL:-}"
  local passthrough=()
  for name in SW_PROBE_DB_URL SW_PROBE_REDIS_URL SW_PROBE_S3_ENDPOINT SW_PROBE_S3_PUBLIC_ENDPOINT SW_PROBE_S3_REGION \
      SW_PROBE_S3_ACCESS SW_PROBE_S3_SECRET SW_PROBE_PRIVATE_BUCKET SW_PROBE_IMAGE_BUCKET SW_PROBE_IMAGE_BASE_URL \
      SW_PROBE_PRESIGN SW_PROBE_PROFILE SW_PROBE_SMTP_HOST SW_PROBE_SMTP_PORT SW_PROBE_SMTP_USER SW_PROBE_SMTP_PASSWORD \
      SW_PROBE_SMTP_FROM SW_PROBE_SMTP_TLS SW_PROBE_TEST_EMAIL_TO SW_PROBE_COMPONENTS SW_PROBE_EXPECT_EMPTY; do
    export "$name"
    passthrough+=(-e "$name")
  done
  if docker run --rm -i --entrypoint python "${passthrough[@]}" "$image" - < "$ROOT/scripts/installer/probe-external.py"; then
    echo 'All outside services passed their tests.'
  else
    echo 'An outside service failed its test. Nothing was started. Fix the setting named above in .env (or the provider) and run setup again.' >&2
    return 1
  fi
}
