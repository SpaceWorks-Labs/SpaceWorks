#!/usr/bin/env bash
# Compose dotenv single quotes suppress interpolation of operator-provided secrets.
source "$(dirname "${BASH_SOURCE[0]}")/installer/outside-services.sh"
env_setting() {
  local value="$2"
  value="${value//\\/\\\\}"
  value="${value//\'/\\\'}"
  printf "%s='%s'\n" "$1" "$value" >> "${3:-.env}"
}

write_setup_environment() {
  [[ "${ANSWERS_CONFIRMED:-}" == yes ]] || die 'Confirm the deployment questions first.'
  if [[ "$HTTPS_MODE" == 1 ]]; then
    [[ "$WEBHOST" == localhost || "$WEBHOST" == 127.0.0.1 ]] \
      || die 'Plain HTTP is restricted to loopback; LAN addresses require HTTPS.'
    [[ "$HOSTING_MODEL" != 3 && "$RUN_FRONTEND" == 1 && -z "${SITE_ORIGINS:-}" ]] \
      || die 'This topology requires HTTPS.'
  fi
  (umask 077; set -o noclobber; : > .env)
  chmod 600 .env
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) python3 "$ROOT/scripts/installer/private_files.py" secure "$ROOT/.env" || return ;;
  esac
  local scheme=http app_url origins proxy_count=1 layer=none
  [[ "$HTTPS_MODE" == 1 ]] || scheme=https
  app_url="$scheme://$WEBHOST"
  [[ "$HOSTING_MODEL" != 3 ]] || app_url="https://$MS_SUBDOMAIN.$PLATFORM_DOMAIN"
  origins="${SITE_ORIGINS:-$app_url}"
  [[ -z "$SITE_ORIGINS" ]] || app_url="${SITE_ORIGINS%%,*}"
  [[ "$HTTPS_MODE" != 2 ]] || layer=tls
  [[ "$HOSTING_MODEL" != 3 ]] || layer=saas
  printf '%s\n' "$layer" > "$ROOT/.spaceworks-layer"
  export SPACEWORKS_COMPOSE_LAYER="$layer"
  # The database-pointer reader accepts literal assignments; generated alphanumerics
  # need no dotenv quotes and must match the passwords Compose gives PostgreSQL.
  printf 'POSTGRES_PASSWORD=%s\nPOSTGRES_APP_PASSWORD=%s\n' "$(rand_key 32)" "$(rand_key 32)" >> .env
  env_setting MINIO_ROOT_USER "$(rand_key 24)"
  env_setting MINIO_ROOT_PASSWORD "$(rand_key 40)"
  env_setting SECRET_KEY "$(rand_key 50)"
  # Deployment identity for PIN hashes: keep .env on updates; never rotate implicitly.
  env_setting EVENT_STATION_PIN_PEPPER "$(rand_key 50)"
  env_setting API_CLIENT_ENC_KEY "$(fernet_key)"
  env_setting AUDIT_MAC_MASTER_KEY "$(fernet_key)"
  # Finance encryption is mandatory even when optional PII encryption is off.
  env_setting PII_MASTER_KEY "$(fernet_key)"
  env_setting PII_SEARCH_HASH_KEY "$(fernet_key)"
  write_continuity_keys .env
  source "$(dirname "${BASH_SOURCE[0]}")/installer/setup-scan.sh"
  write_setup_scanner_environment || die 'Invalid scanner selection.'
  configure_release_repository || die 'Invalid GitHub repository.'
  env_setting SPACEWORKS_REPOSITORY "$SPACEWORKS_REPOSITORY"
  env_setting MAKERSPACE_BACKEND_IMAGE "$MAKERSPACE_BACKEND_IMAGE"
  env_setting MAKERSPACE_FRONTEND_IMAGE "$MAKERSPACE_FRONTEND_IMAGE"
  env_setting SPACEWORKS_OPS_HOST_DIR "${SPACEWORKS_OPS_HOST_DIR:-/var/lib/spaceworks/ops}"
  env_setting SPACEWORKS_HOST_STATE_DIR "${SPACEWORKS_HOST_STATE_DIR:-/var/lib/spaceworks/host}"
  env_setting SPACEWORKS_HOSTING_MODEL "$HOSTING_MODEL"
  env_setting SPACEWORKS_RUN_FRONTEND "$([[ "$RUN_FRONTEND" == 1 ]] && echo yes || echo no)"
  env_setting SPACEWORKS_STORAGE "$([[ "$STORAGE" == 1 ]] && echo bundled || echo external)"
  env_setting SPACEWORKS_EDITION "$SPACEWORKS_EDITION"
  # Scheduler mode is unquoted: the topology authority reads this key literally.
  echo 'SPACEWORKS_SCHEDULER_MODE=image' >> .env
  env_setting ALLOWED_HOSTS "$WEBHOST,localhost,127.0.0.1,backend"
  env_setting CORS_ALLOWED_ORIGINS "$origins"
  env_setting CSRF_TRUSTED_ORIGINS "$origins"
  env_setting PUBLIC_APP_BASE_URL "$app_url"
  env_setting HTTP_PORT "$([[ "$HTTPS_MODE" == 3 ]] && echo 8080 || echo 80)"
  env_setting ENABLE_HTTPS "$([[ "$HTTPS_MODE" == 1 ]] && echo false || echo true)"
  # Insecure cookies are permitted only after the loopback-only check above.
  env_setting AUTH_COOKIE_SECURE "$([[ "$HTTPS_MODE" == 1 ]] && echo false || echo true)"
  env_setting AUTH_COOKIE_SAMESITE "$([[ "$HTTPS_MODE" == 1 ]] && echo Lax || echo None)"
  env_setting HUB_LANDING_ENABLED "$([[ "${SETUP_HUB_LANDING:-Y}" =~ ^[Yy] ]] && echo true || echo false)"
  env_setting CONTROL_PLANE_PROXY "${CONTROL_PLANE_PROXY:-false}"
  [[ -z "${CONTROL_PLANE_ALLOW_CIDRS:-}" ]] || env_setting CONTROL_PLANE_ALLOW_CIDRS "$CONTROL_PLANE_ALLOW_CIDRS"
  [[ -z "${CONTROL_PLANE_TUNNEL_PORT:-}" ]] || env_setting CONTROL_PLANE_TUNNEL_PORT "$CONTROL_PLANE_TUNNEL_PORT"
  env_setting TRUST_X_FORWARDED_PROTO "$([[ "$HTTPS_MODE" == 1 ]] && echo false || echo true)"
  if [[ "$HTTPS_MODE" == 1 ]]; then
    env_setting HTTP_PORT_BIND 127.0.0.1
    env_setting API_BIND 127.0.0.1
    env_setting MINIO_API_BIND 127.0.0.1
    env_setting MINIO_CONSOLE_BIND 127.0.0.1
  fi
  if [[ "$HTTPS_MODE" == 3 ]]; then
    env_setting HTTP_PORT_BIND 127.0.0.1
    env_setting API_BIND 127.0.0.1
    env_setting API_PORT 8080
    proxy_count=2
  fi
  env_setting TRUSTED_PROXY_COUNT "$proxy_count"
  env_setting PUBLIC_DOMAIN "$PUBLIC_DOMAIN"
  env_setting TLS_EMAIL "$TLS_EMAIL"
  if [[ "$HOSTING_MODEL" == 3 ]]; then
    env_setting CADDY_SAAS_CONFIG ./deploy/Caddyfile.saas-install
    env_setting PLATFORM_DOMAIN "$PLATFORM_DOMAIN"
    env_setting PLATFORM_FIRST_HOST "$MS_SUBDOMAIN.$PLATFORM_DOMAIN"
    env_setting PLATFORM_DOMAIN_SUFFIX ".$PLATFORM_DOMAIN"
    env_setting PLATFORM_SUBDOMAIN_AUTO_TLS true
    env_setting PLATFORM_ORIGIN_HOST "origin.$PLATFORM_DOMAIN"
    env_setting BEHIND_TRUSTED_PROXY true
    env_setting PLATFORM_STAFF_ORIGINS "https://$PLATFORM_DOMAIN${SITE_ORIGINS:+,${SITE_ORIGINS%%,*}}"
    env_setting INFRA_HOSTS "localhost,127.0.0.1,backend,origin.$PLATFORM_DOMAIN,files.$PLATFORM_DOMAIN,$MS_SUBDOMAIN.$PLATFORM_DOMAIN,$PLATFORM_DOMAIN"
  fi
  # The superadmin signs in only from a platform origin (release 2). On a self-host the
  # platform console is the site itself; a hosted platform sets its own above.
  [[ "$HOSTING_MODEL" == 3 ]] || env_setting PLATFORM_STAFF_ORIGINS "$app_url"
  env_setting SPACEWORKS_WEB_UPSTREAM "$([[ "$RUN_FRONTEND" == 1 ]] && echo frontend:80 || echo api-edge:80)"
  if [[ "$STORAGE" == 2 ]]; then
    env_setting AWS_S3_ENDPOINT_URL "$S3_ENDPOINT"
    env_setting AWS_S3_PUBLIC_ENDPOINT_URL "${S3_PUBLIC_ENDPOINT:-$S3_ENDPOINT}"
    env_setting AWS_S3_REGION_NAME "$S3_REGION"
    env_setting AWS_ACCESS_KEY_ID "$S3_ACCESS_KEY"
    env_setting AWS_SECRET_ACCESS_KEY "$S3_SECRET_KEY"
    env_setting AWS_STORAGE_BUCKET_NAME "$PRIVATE_BUCKET"
    env_setting PUBLIC_IMAGE_BUCKET "$IMAGE_BUCKET"
    env_setting PUBLIC_IMAGE_BASE_URL "$IMAGE_BASE_URL"
    env_setting STORAGE_PRESIGN_METHOD "$PRESIGN_METHOD"
  elif [[ "$HTTPS_MODE" != 1 ]]; then
    local storage_host="files.${PLATFORM_DOMAIN:-$WEBHOST}"
    env_setting STORAGE_DOMAIN "$storage_host"
    env_setting STORAGE_CADDY_CONFIG /etc/caddy/storage.caddy
    env_setting AWS_S3_PUBLIC_ENDPOINT_URL "https://$storage_host"
    env_setting PUBLIC_IMAGE_BASE_URL "https://$storage_host/public-images"
    env_setting MINIO_CORS_ALLOWED_ORIGINS "$origins"
    env_setting MINIO_API_BIND 127.0.0.1
  else
    env_setting AWS_S3_PUBLIC_ENDPOINT_URL "http://$WEBHOST:9000"
    env_setting PUBLIC_IMAGE_BASE_URL "http://$WEBHOST:9000/public-images"
    env_setting MINIO_CORS_ALLOWED_ORIGINS "$origins"
  fi
  write_outside_environment || return
  source "$(dirname "${BASH_SOURCE[0]}")/installer/environment-continuity.sh"
  forward_installer_environment || return
}

# Encryption/fingerprint keys a fresh install generates. An operator-supplied value
# (for example recovered from escrow) is written instead of a generated one.
continuity_key_value() {
  case "$1" in
    PUSH_TOKEN_HMAC_KEY) rand_key 64 ;;
    ACCOUNT_PII_MASTER_KEY) fernet_key ;;
    EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY) head -c 32 /dev/urandom | base64 ;;
    EVENT_REGISTRATION_CREDENTIAL_KEYS) printf '{"1":"%s"}' "$(head -c 32 /dev/urandom | base64)" ;;
  esac
}

write_continuity_keys() {
  local target="$1" name
  for name in PUSH_TOKEN_HMAC_KEY ACCOUNT_PII_MASTER_KEY \
      EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY EVENT_REGISTRATION_CREDENTIAL_KEYS; do
    env_setting "$name" "${!name:-$(continuity_key_value "$name")}" "$target"
    [[ "$name" != EVENT_REGISTRATION_CREDENTIAL_KEYS || -n "${EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION:-}" ]] \
      || env_setting EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION 1 "$target"
  done
}

# Upgrades never regenerate or replace a key. A key that was never declared cannot
# have protected anything (each consumer refuses without it), so it is added once.
backfill_absent_continuity_keys() {
  local name broker
  broker="$(deployment_value ACCOUNT_PII_KEY_BROKER)"
  # Appended assignments must start on their own line.
  [[ ! -s "$ROOT/.env" || -z "$(tail -c 1 "$ROOT/.env")" ]] || printf '\n' >> "$ROOT/.env"
  for name in PUSH_TOKEN_HMAC_KEY ACCOUNT_PII_MASTER_KEY \
      EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY EVENT_REGISTRATION_CREDENTIAL_KEYS; do
    grep -q "^$name=" "$ROOT/.env" && continue
    [[ -n "${!name:-}" || "$name" != ACCOUNT_PII_MASTER_KEY || "${broker:-local}" == local ]] || continue
    env_setting "$name" "${!name:-$(continuity_key_value "$name")}" "$ROOT/.env" || return
    if [[ "$name" == EVENT_REGISTRATION_CREDENTIAL_KEYS ]] \
        && ! grep -q '^EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION=' "$ROOT/.env"; then
      env_setting EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION 1 "$ROOT/.env" || return
    fi
  done
  chmod 600 "$ROOT/.env"
}

# Release 2 lets the superadmin sign in only from PLATFORM_STAFF_ORIGINS. A self-host set up
# before it has none, which would lock the superadmin out of the web console after the
# update: add the site's own origin once. A hosted platform (model 3) already has its own.
backfill_platform_staff_origin() {
  local origin
  grep -q '^PLATFORM_STAFF_ORIGINS=' "$ROOT/.env" && return 0
  [[ "$(deployment_value SPACEWORKS_HOSTING_MODEL)" != 3 ]] || return 0
  origin="$(deployment_value PUBLIC_APP_BASE_URL)"
  [[ "$origin" =~ ^https?://[^/[:space:],]+$ ]] || return 0
  [[ ! -s "$ROOT/.env" || -z "$(tail -c 1 "$ROOT/.env")" ]] || printf '\n' >> "$ROOT/.env"
  env_setting PLATFORM_STAFF_ORIGINS "$origin" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
}

# Opt-in free profile: a private .env from the reviewed template with every secret
# generated here, the same way the full profile generates its own. No service starts.
write_free_profile_environment() {
  local template="$ROOT/deploy/cloud/free.env.example" line name value
  [[ -f "$template" ]] || die 'The free-profile environment template is missing from this release.'
  (umask 077; set -o noclobber; : > .env)
  chmod 600 .env
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) python3 "$ROOT/scripts/installer/private_files.py" secure "$ROOT/.env" || return ;;
  esac
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^([A-Z][A-Z0-9_]*)=\"(.*)\"$ ]] || continue
    name="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"
    case "$name" in
      SECRET_KEY|EVENT_STATION_PIN_PEPPER) value="$(rand_key 50)" ;;
      FREE_TICK_SECRET) value="$(rand_key 48)" ;;
      API_CLIENT_ENC_KEY|AUDIT_MAC_MASTER_KEY|PII_MASTER_KEY|PII_SEARCH_HASH_KEY) value="$(fernet_key)" ;;
      SPACEWORKS_DEPLOYMENT_ID) value="$(python3 -c 'import uuid; print(uuid.uuid4())')" ;;
    esac
    env_setting "$name" "$value"
  done < "$template"
  write_continuity_keys .env
  env_setting SPACEWORKS_REPOSITORY "${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}"
}

print_key_backup_notice() {
  echo '  Back up the private .env now and keep the copy off this server: SECRET_KEY,'
  echo '  API_CLIENT_ENC_KEY, AUDIT_MAC_MASTER_KEY, PII_MASTER_KEY, PII_SEARCH_HASH_KEY,'
  echo '  ACCOUNT_PII_MASTER_KEY, EVENT_REGISTRATION_CREDENTIAL_* and PUSH_TOKEN_HMAC_KEY cannot'
  echo '  be regenerated: losing or changing one makes the data it protects unreadable.'
}
