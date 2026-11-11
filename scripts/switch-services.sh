#!/usr/bin/env bash
# Move one component of a running install between this server and an outside service (decision 239).
#   bash scripts/switch-services.sh status
#   bash scripts/switch-services.sh redis | email | storage [--files-copied] | database
#   bash scripts/switch-services.sh menu      (the installer's "Change outside services" choice)
# Nothing that holds data moves silently: a database switch is refused with the exact data-move
# steps, and a storage switch needs --files-copied once you have copied the objects yourself.
set -euo pipefail

SWITCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SPACEWORKS_UPDATE_INSTALL_DIR:-$(cd "$SWITCH_DIR/.." && pwd)}"
cd "$ROOT"
export SPACEWORKS_UPDATE_INSTALL_DIR="$ROOT" SPACEWORKS_STATIC_ENV_FILE="$ROOT/.env"
source "$SWITCH_DIR/install-owner.sh"
require_install_owner "$SWITCH_DIR/switch-services.sh" "$@"
say() { printf '[Space Works services] %s\n' "$*"; }
die() { printf '[Space Works services] ERROR: %s\n' "$*" >&2; exit 1; }
refuse() { printf '[Space Works services] %s\n' "$*" >&2; exit 64; }
source "$SWITCH_DIR/compose-deployment.sh"
source "$SWITCH_DIR/setup-question-input.sh"
source "$SWITCH_DIR/setup-write-environment.sh"
source "$SWITCH_DIR/installer/outside-checks.sh"
[[ -f "$ROOT/.env" ]] || die 'No .env here: run setup.sh first.'

COMPONENT="${1:-status}"; FILES_COPIED=0
[[ "${2:-}" != --files-copied ]] || FILES_COPIED=1
# Installer entry: pick the component from a short menu. Enter (or anything else) cancels.
if [[ "$COMPONENT" == menu ]]; then
  SWITCH_MENU_TTY="${SPACEWORKS_INSTALL_TEST_TTY:-/dev/tty}"
  printf '%s
' 'Change outside services - which one?' '  1) Database   2) Redis   3) File storage   4) Email' >&2
  printf 'Choose 1-4 [Enter = cancel]: ' >&2
  IFS= read -r menu_choice < "$SWITCH_MENU_TTY" || menu_choice=''
  case "$menu_choice" in
    1) COMPONENT=database ;;
    2) COMPONENT=redis ;;
    3) COMPONENT=storage
       printf 'Have you already copied the objects to the new storage? [y/N]: ' >&2
       IFS= read -r menu_copied < "$SWITCH_MENU_TTY" || menu_copied=''
       [[ ! "$menu_copied" =~ ^[Yy] ]] || FILES_COPIED=1 ;;
    4) COMPONENT=email ;;
    *) echo 'Cancelled; nothing was changed.'; exit 130 ;;
  esac
fi
SETUP_NON_INTERACTIVE=0
[[ "$COMPONENT" == status ]] || exec 3</dev/tty

show_status() {
  local db redis storage
  db="$(deployment_value SPACEWORKS_DATABASE)"; redis="$(deployment_value SPACEWORKS_REDIS)"
  storage="$(deployment_value SPACEWORKS_STORAGE)"
  printf 'Database: %s\nRedis:    %s\nStorage:  %s\nEmail:    %s\nWebsite:  %s\n' \
    "$([[ "$db" == external ]] && echo 'outside PostgreSQL' || echo 'on this server')" \
    "$([[ "$redis" == external ]] && echo 'outside Redis' || echo 'on this server')" \
    "$([[ "$storage" == external ]] && echo 'outside S3-compatible storage' || echo 'on this server')" \
    "$([[ -n "$(deployment_value EMAIL_HOST)" ]] && echo "SMTP $(deployment_value EMAIL_HOST)" || echo 'set in the control panel')" \
    "$([[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" == no ]] && echo 'not on this server (API-only)' || echo 'on this server')"
}

refuse_database_switch() {
  cat >&2 <<'MESSAGE'
Switching the database moves every record, so it is never done silently or in place.
Use the backup and restore tools that already ship with Space Works:
  1. Back up now: Settings > Backups (or the pre-update dump that scripts/update.sh writes to backups/).
  2. Install a NEW copy of Space Works that points at the new database: run setup.sh in a new folder,
     choose "An outside server" under Outside services, and give an EMPTY database (setup refuses a
     database that already has tables, so nothing is overwritten).
  3. In the new install, restore the backup: scripts/import-backup.sh <archive> <superadmin>.
  4. Check the new install, then retire the old one. The old database is untouched until you remove it.
Going from an outside database back to this server follows the same steps in reverse.
MESSAGE
  exit 64
}

# Replace the named keys in .env (one atomic rename), keeping the previous file as .env.before-services.
rewrite_env() {
  local temp keys=("$@") key pattern=''
  cp -p -- "$ROOT/.env" "$ROOT/.env.before-services"
  for key in "${keys[@]}"; do pattern+="${pattern:+\\|}$key"; done
  temp="$(umask 077; mktemp "$ROOT/.env.services.XXXXXX")"
  sed "/^[[:space:]]*\\(export[[:space:]]\\+\\)\\?\\($pattern\\)=/d" "$ROOT/.env" > "$temp"
  [[ ! -s "$temp" || -z "$(tail -c 1 "$temp")" ]] || printf '\n' >> "$temp"
  chmod 600 "$temp"
  mv -f -- "$temp" "$ROOT/.env"
}

# Test the new settings, then apply them with the control-plane applier (refreshes the topology
# record, restarts, probes). A failure puts the previous .env back.
apply_services() {
  local container
  container="$("$ROOT/scripts/spaceworks-compose.sh" bundled ps -q backend | head -n 1)"
  [[ -n "$container" ]] || die 'The backend service must be running to switch a service.'
  HOST_CONFIG_IMAGE="$(docker inspect --format '{{.Image}}' "$container")"
  export HOST_CONFIG_IMAGE
  if ! run_outside_checks; then
    cp -p -- "$ROOT/.env.before-services" "$ROOT/.env"
    die 'The new service failed its test, so nothing changed (your previous .env is back in place).'
  fi
  if ! bash "$SWITCH_DIR/apply-settings.sh"; then
    cp -p -- "$ROOT/.env.before-services" "$ROOT/.env"
    die 'Applying failed; your previous .env is back. Run: bash scripts/apply-settings.sh'
  fi
  say 'Done. Check the site, then run the install-and-update guide checks (docs/install-and-update.md, Hybrid setup).'
}

switch_redis() {
  local current choice url confirm
  current="$(deployment_value SPACEWORKS_REDIS)"; current="${current:-bundled}"
  ask_outside_redis || die 'Cancelled.'
  [[ "$REDIS_CHOICE" == 2 ]] && choice=external || choice=bundled
  [[ "$choice" != external ]] || url="$(normalize_redis_url "$EXTERNAL_REDIS_URL")"
  [[ "$choice" != "$current" || "$choice" == external ]] || { say 'Redis is already on this server; nothing to change.'; return 0; }
  echo 'Jobs still waiting in the current Redis are dropped by this switch; scheduled work resumes on its own.'
  question confirm 'Switch Redis now?' N choices:Y,y,yes,YES,N,n,no,NO || die 'Cancelled.'
  [[ "$confirm" =~ ^[Yy] ]] || die 'Cancelled; nothing changed.'
  rewrite_env SPACEWORKS_REDIS CELERY_BROKER_URL CACHE_URL LIVE_REDIS_URL
  env_setting SPACEWORKS_REDIS "$choice"
  [[ "$choice" != external ]] || env_setting CELERY_BROKER_URL "$url"
  apply_services
}

switch_email() {
  ADMINEMAIL=''
  ask_outside_email || die 'Cancelled.'
  if [[ "$EMAIL_CHOICE" == 2 && "$SMTP_TEST" =~ ^[Yy] ]]; then
    question ADMINEMAIL 'Send the test email to' '' email || die 'Cancelled.'
  fi
  rewrite_env EMAIL_HOST EMAIL_PORT EMAIL_HOST_USER EMAIL_HOST_PASSWORD EMAIL_USE_TLS DEFAULT_FROM_EMAIL
  [[ "$EMAIL_CHOICE" != 2 ]] || write_outside_environment_email
  apply_services
}

write_outside_environment_email() {
  env_setting EMAIL_HOST "$SMTP_HOST"; env_setting EMAIL_PORT "$SMTP_PORT"
  env_setting EMAIL_HOST_USER "$SMTP_USER"; env_setting EMAIL_HOST_PASSWORD "$SMTP_PASSWORD"
  env_setting EMAIL_USE_TLS "$([[ "$SMTP_TLS" =~ ^[Yy] ]] && echo True || echo False)"
  env_setting DEFAULT_FROM_EMAIL "$SMTP_FROM"
}

switch_storage() {
  [[ "$FILES_COPIED" == 1 ]] || {
    cat >&2 <<'MESSAGE'
Storage holds your evidence photos, so objects are not copied automatically.
1. Create the two buckets at the new provider and copy the objects first, for example with the MinIO client:
     mc alias set old <old endpoint> <key> <secret> && mc alias set new <new endpoint> <key> <secret>
     mc mirror old/<private bucket> new/<private bucket> && mc mirror old/<public bucket> new/<public bucket>
2. Then run: bash scripts/switch-services.sh storage --files-copied
MESSAGE
    exit 64
  }
  HTTPS_MODE=1; [[ "$(deployment_value ENABLE_HTTPS)" != true ]] || HTTPS_MODE=2
  ask_outside_storage || die 'Cancelled.'
  [[ "$STORAGE" == 2 ]] || refuse 'Moving files back onto this server is a reinstall-time choice; see docs/install-and-update.md, Hybrid setup.'
  rewrite_env SPACEWORKS_STORAGE AWS_S3_ENDPOINT_URL AWS_S3_PUBLIC_ENDPOINT_URL AWS_S3_REGION_NAME AWS_ACCESS_KEY_ID \
    AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME PUBLIC_IMAGE_BUCKET PUBLIC_IMAGE_BASE_URL STORAGE_PRESIGN_METHOD \
    STORAGE_CAPABILITIES_FILE STORAGE_DOMAIN STORAGE_CADDY_CONFIG MINIO_CORS_ALLOWED_ORIGINS
  env_setting SPACEWORKS_STORAGE external
  env_setting AWS_S3_ENDPOINT_URL "$S3_ENDPOINT"; env_setting AWS_S3_PUBLIC_ENDPOINT_URL "${S3_PUBLIC_ENDPOINT:-$S3_ENDPOINT}"
  env_setting AWS_S3_REGION_NAME "$S3_REGION"; env_setting AWS_ACCESS_KEY_ID "$S3_ACCESS_KEY"
  env_setting AWS_SECRET_ACCESS_KEY "$S3_SECRET_KEY"; env_setting AWS_STORAGE_BUCKET_NAME "$PRIVATE_BUCKET"
  env_setting PUBLIC_IMAGE_BUCKET "$IMAGE_BUCKET"; env_setting PUBLIC_IMAGE_BASE_URL "$IMAGE_BASE_URL"
  env_setting STORAGE_PRESIGN_METHOD "$PRESIGN_METHOD"
  write_storage_capabilities_file
  env_setting STORAGE_CAPABILITIES_FILE /run/spaceworks-storage/capabilities.json
  apply_services
}

case "$COMPONENT" in
  status) show_status ;;
  database) refuse_database_switch ;;
  redis) switch_redis ;;
  email) switch_email ;;
  storage) switch_storage ;;
  *) refuse 'Usage: bash scripts/switch-services.sh status | menu | redis | email | storage [--files-copied] | database' ;;
esac
