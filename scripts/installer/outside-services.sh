#!/usr/bin/env bash
# "Outside services (optional)" - decision 239. Every component runs on this server unless the
# operator names an outside one. No filesystem or Docker effects here: questions only, then
# write_outside_environment (called by write_setup_environment) records the answers in .env.
#
# Answer keys: DATABASE_CHOICE (1 local, 2 outside) EXTERNAL_DB_URL EXTERNAL_DB_DIRECT_URL
#   REDIS_CHOICE (1 local, 2 outside, 3 none = cron mode) EXTERNAL_REDIS_URL
#   STORAGE (1 local, 2 S3-compatible) S3_ENDPOINT S3_PUBLIC_ENDPOINT S3_REGION PRIVATE_BUCKET
#   IMAGE_BUCKET S3_ACCESS_KEY S3_SECRET_KEY IMAGE_BASE_URL STORAGE_PROFILE (limited|full) PRESIGN_METHOD
#   EMAIL_CHOICE (1 later in the control panel, 2 SMTP now) SMTP_HOST SMTP_PORT SMTP_USER
#   SMTP_PASSWORD SMTP_TLS SMTP_FROM SMTP_TEST. The website is the RUN_FRONTEND/SITE_ORIGINS answers.

OUTSIDE_DB_PATTERN='^(postgres|postgresql)://([^:@/]+)(:([^@/]*))?@([^:/?#@]+)(:([0-9]+))?/([^?#]+)(\?([^#]*))?$'

outside_defaults() {
  DATABASE_CHOICE=${DATABASE_CHOICE:-1}; EXTERNAL_DB_URL=${EXTERNAL_DB_URL:-}; EXTERNAL_DB_DIRECT_URL=${EXTERNAL_DB_DIRECT_URL:-}
  REDIS_CHOICE=${REDIS_CHOICE:-1}; EXTERNAL_REDIS_URL=${EXTERNAL_REDIS_URL:-}
  STORAGE=${STORAGE:-1}; STORAGE_PROFILE=${STORAGE_PROFILE:-limited}; S3_PUBLIC_ENDPOINT=${S3_PUBLIC_ENDPOINT:-}
  EMAIL_CHOICE=${EMAIL_CHOICE:-1}; SMTP_HOST=${SMTP_HOST:-}; SMTP_PORT=${SMTP_PORT:-587}; SMTP_USER=${SMTP_USER:-}
  SMTP_PASSWORD=${SMTP_PASSWORD:-}; SMTP_TLS=${SMTP_TLS:-Y}; SMTP_FROM=${SMTP_FROM:-}; SMTP_TEST=${SMTP_TEST:-N}
}

# Sets DB_USER DB_PASS DB_HOST DB_PORT DB_NAME DB_QUERY from a postgres URL.
db_url_parts() {
  [[ "$1" =~ $OUTSIDE_DB_PATTERN ]] || return 1
  DB_USER="${BASH_REMATCH[2]}"; DB_PASS="${BASH_REMATCH[4]}"; DB_HOST="${BASH_REMATCH[5]}"
  DB_PORT="${BASH_REMATCH[7]:-5432}"; DB_NAME="${BASH_REMATCH[8]}"; DB_QUERY="${BASH_REMATCH[10]}"
}

outside_host_is_private() {
  case "$1" in
    localhost|127.*|::1|db|redis|10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*) return 0 ;;
  esac
  return 1
}

# A transaction pooler hands every statement to a different server connection; the application
# holds advisory locks and pg_dump/migrations cannot work through one.
db_url_is_transaction_pooler() {
  [[ "$DB_HOST" =~ \.supabase\.(co|com|net)$ && "$DB_PORT" == 6543 ]] && return 0
  [[ "$DB_HOST" == *.neon.tech && "${DB_HOST%%.*}" == *-pooler ]] && return 0
  return 1
}

db_url_is_pooler() {
  db_url_parts "$1" || return 1
  db_url_is_transaction_pooler && return 0
  [[ "$DB_HOST" == *.pooler.* ]]
}

# Prints the reason and returns 1 when the URL cannot be used. Never prints the URL itself.
db_url_problem() {
  local url="$1"
  [[ "$url" != *\'* && "$url" != *\\* && "$url" != *[[:space:]]* ]] \
    || { echo 'The URL must not contain quotes, backslashes or spaces; percent-encode special characters in the password.'; return 1; }
  db_url_parts "$url" \
    || { echo 'Use postgresql://user:password@host:5432/database?sslmode=require (percent-encode @ : / ? # in the password).'; return 1; }
  if db_url_is_transaction_pooler; then
    echo 'That is a transaction-pooler address. Space Works needs the direct connection or the session pooler: Supabase port 5432 (not 6543), Neon the host without -pooler.'
    return 1
  fi
  if ! outside_host_is_private "$DB_HOST"; then
    [[ "$DB_QUERY" =~ (^|&)sslmode=(require|verify-ca|verify-full)(&|$) ]] \
      || { echo 'A database on another network must use TLS: add ?sslmode=require (or verify-full) to the URL.'; return 1; }
  fi
  return 0
}

redis_url_problem() {
  local url="$1" host
  [[ "$url" =~ ^rediss?://[^[:space:]\'\"\\]+$ ]] || { echo 'Use rediss://default:password@host:6379 (the TLS address your provider shows).'; return 1; }
  host="${url#*://}"; host="${host##*@}"; host="${host%%[:/?]*}"
  if [[ "$url" == redis://* ]] && ! outside_host_is_private "$host"; then
    echo 'An outside Redis must be reached over TLS: use the rediss:// address, not redis://.'
    return 1
  fi
}

# Celery refuses a rediss:// broker that does not say how to verify the certificate.
normalize_redis_url() {
  local url="$1"
  if [[ "$url" == rediss://* && "$url" != *ssl_cert_reqs=* ]]; then
    [[ "$url" == *\?* ]] && url+='&ssl_cert_reqs=required' || url+='?ssl_cert_reqs=required'
  fi
  printf '%s' "$url"
}

# $1 primary URL  $2 runtime login  $3 runtime password. A Supabase pooler login is "role.projectref".
derive_runtime_database_url() {
  local user="$2"
  db_url_parts "$1" || return 1
  if [[ "$DB_HOST" == *.pooler.supabase.* && "$DB_USER" == *.* ]]; then user="$user.${DB_USER#*.}"; fi
  printf 'postgres://%s:%s@%s:%s/%s%s' "$user" "$3" "$DB_HOST" "$DB_PORT" "$DB_NAME" "${DB_QUERY:+?$DB_QUERY}"
}

# The answer number as the word SPACEWORKS_REDIS and compose-deployment.sh use.
redis_choice_word() {
  case "$1" in 2) echo external ;; 3) echo none ;; *) echo bundled ;; esac
}

normalize_postgres_scheme() { printf 'postgres://%s' "${1#*://}"; }

ask_outside_database() {
  echo 'Database (PostgreSQL 16 or 17):'
  echo '  1) On this server - bundled PostgreSQL 16 (recommended).'
  echo '  2) An outside server - Supabase, Neon, Amazon RDS or your own. You paste its connection URL.'
  question DATABASE_CHOICE 'Database' 1 choices:1,2 || return 1
  [[ "$DATABASE_CHOICE" == 2 ]] || return 0
  echo 'Use the owner login (for Supabase, the postgres user) with the direct connection or the session pooler.'
  echo 'Space Works creates its own limited login on that server; the owner login is used only to set it up.'
  question EXTERNAL_DB_URL 'Database URL' '' postgres_url || return 1
  if db_url_is_pooler "$EXTERNAL_DB_URL"; then
    echo 'That address goes through a pooler. Migrations and backups need the direct (or session-mode) connection too.'
    question EXTERNAL_DB_DIRECT_URL 'Direct database URL for migrations and backups' '' postgres_url || return 1
  fi
}

ask_outside_redis() {
  echo 'Redis (queue, cache and live updates):'
  echo '  1) On this server - bundled Redis (recommended).'
  echo '  2) An outside Redis - Upstash, Redis Cloud, ElastiCache or your own. You paste its rediss:// URL.'
  echo '  3) None (cron mode) - no Redis, no worker and no beat. Background jobs run inside the request that starts'
  echo '     them, scheduled jobs run once a minute from a scheduler container (run_scheduled_tasks), and live'
  echo '     screens poll instead of streaming. Fine for a small space; choose 1 if many people use it at once.'
  question REDIS_CHOICE 'Redis' 1 choices:1,2,3 || return 1
  [[ "$REDIS_CHOICE" == 2 ]] || return 0
  question EXTERNAL_REDIS_URL 'Redis URL' '' redis_url || return 1
}

ask_outside_storage() {
  echo 'File storage:'
  echo '  1) On this server - bundled Silo object storage (private evidence and public images).'
  echo '  2) An outside S3-compatible service - Cloudflare R2, Backblaze B2, Amazon S3, Supabase Storage...'
  question STORAGE 'File storage' 1 choices:1,2 || return 1
  S3_ENDPOINT=''; S3_REGION=us-east-1; PRIVATE_BUCKET=evidence; IMAGE_BUCKET=public-images
  S3_ACCESS_KEY=''; S3_SECRET_KEY=''; IMAGE_BASE_URL=''; PRESIGN_METHOD=post
  [[ "$STORAGE" == 2 ]] || return 0
  local rule=url
  [[ "$HTTPS_MODE" == 1 ]] || rule=secure_url
  question S3_ENDPOINT 'S3 endpoint' '' "$rule" || return 1
  question S3_PUBLIC_ENDPOINT 'Address browsers use for uploads (Enter = the same endpoint)' "$S3_ENDPOINT" "$rule" || return 1
  question S3_REGION 'S3 region (auto for Cloudflare R2)' us-east-1 region || return 1
  question PRIVATE_BUCKET 'Private evidence bucket' evidence bucket || return 1
  while true; do
    question IMAGE_BUCKET 'Public-image bucket' public-images bucket || return 1
    [[ "$IMAGE_BUCKET" != "$PRIVATE_BUCKET" ]] && break
    echo 'Private evidence and public images must use different buckets.'
  done
  question S3_ACCESS_KEY 'S3 access key' '' text || return 1
  while true; do
    question S3_SECRET_KEY 'S3 secret key' '' secret || return 1
    [[ -n "$S3_SECRET_KEY" ]] && break
    echo 'A secret key is required.'
  done
  question IMAGE_BASE_URL 'Public image base URL (includes bucket/path)' '' "$rule" || return 1
  echo 'What can this storage do? limited = Cloudflare R2, Backblaze B2, Supabase Storage and most others'
  echo '(upload size is checked after upload, no version history). full = Amazon S3 or MinIO with versioning on.'
  # An answers file written before profiles existed names only a presign method: post meant full parity.
  local profile_default=limited
  if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 && -z "${INPUT_ANSWERS[STORAGE_PROFILE]+present}"       && "${INPUT_ANSWERS[PRESIGN_METHOD]:-}" == post ]]; then profile_default=full; fi
  question STORAGE_PROFILE 'Storage profile' "$profile_default" choices:limited,full || return 1
  if [[ "$STORAGE_PROFILE" == full ]]; then
    question PRESIGN_METHOD 'Presign method' post choices:put,post || return 1
  else
    PRESIGN_METHOD=put
    if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 && -n "${INPUT_ANSWERS[PRESIGN_METHOD]+present}" ]]; then
      INPUT_USED[PRESIGN_METHOD]=1
      [[ "${INPUT_ANSWERS[PRESIGN_METHOD]}" == put ]]         || { echo 'A limited storage profile uploads with put; use STORAGE_PROFILE=full for post.' >&2; return 64; }
    fi
  fi
}

ask_outside_email() {
  echo 'Email:'
  echo '  1) Set it up later in the control panel (Resend, Postmark, Brevo, SES, Mailgun, SendGrid or SMTP).'
  echo '  2) Use an SMTP server now.'
  question EMAIL_CHOICE 'Email' 1 choices:1,2 || return 1
  [[ "$EMAIL_CHOICE" == 2 ]] || return 0
  question SMTP_HOST 'SMTP host' '' host || return 1
  question SMTP_PORT 'SMTP port' 587 integer:1:65535 || return 1
  question SMTP_USER 'SMTP user (blank = none)' '' optional || return 1
  question SMTP_PASSWORD 'SMTP password (blank = none)' '' secret || return 1
  question SMTP_TLS 'Use STARTTLS (port 587)?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
  question SMTP_FROM 'Sender address (verified with the provider)' '' email || return 1
  question SMTP_TEST 'Send a test email to the admin address before finishing?' N choices:Y,y,yes,YES,N,n,no,NO || return 1
}

# Full questionnaire only: quick setup keeps everything on this server. File storage is always
# asked (as before); one gate then covers the database, Redis and email so the usual all-local
# install answers a single question. A noninteractive answers file opens the gate by naming any of them.
ask_outside_services() {
  local more=N key
  echo
  echo 'Outside services (optional). Everything runs on this server unless you name an outside one.'
  ask_outside_storage || return 1
  if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 ]]; then
    for key in DATABASE_CHOICE REDIS_CHOICE EMAIL_CHOICE; do
      [[ -z "${INPUT_ANSWERS[$key]+present}" ]] || more=Y
    done
  else
    echo 'Database, Redis and email also run on this server by default (bundled PostgreSQL and Redis; email set up in the control panel).'
    question more 'Use an outside database, Redis or email server instead of any of those?' N choices:Y,y,yes,YES,N,n,no,NO || return 1
  fi
  if [[ "$more" =~ ^[Yy] ]]; then
    ask_outside_database || return 1
    ask_outside_redis || return 1
    ask_outside_email || return 1
  fi
  echo 'The website is chosen above (Full, or hosted elsewhere / none with API-only).'
}

outside_summary() {
  outside_defaults
  local db=local redis=local email='set up later in the control panel'
  [[ "$DATABASE_CHOICE" != 2 ]] || { db='outside PostgreSQL'; [[ -z "$EXTERNAL_DB_DIRECT_URL" ]] || db+=' (pooler + direct URL for migrations)'; }
  [[ "$REDIS_CHOICE" != 2 ]] || redis='outside Redis'
  [[ "$REDIS_CHOICE" != 3 ]] || redis='none (cron mode)'
  [[ "$EMAIL_CHOICE" != 2 ]] || email="SMTP $SMTP_HOST:$SMTP_PORT"
  printf '  Outside services: database %s; Redis %s; email: %s\n' "$db" "$redis" "$email"
  [[ "$STORAGE" != 2 ]] || printf '  Storage profile: %s (%s upload)\n' "$STORAGE_PROFILE" "$PRESIGN_METHOD"
  [[ "$DATABASE_CHOICE" != 2 && "$REDIS_CHOICE" != 2 && "$STORAGE" != 2 && "$EMAIL_CHOICE" != 2 ]] \
    || echo '  Each outside service is tested before setup finishes; nothing is started if a test fails.'
}

# Writes the .env settings for the outside components. Called inside write_setup_environment.
write_outside_environment() {
  outside_defaults
  env_setting SPACEWORKS_DATABASE "$([[ "$DATABASE_CHOICE" == 2 ]] && echo external || echo bundled)"
  env_setting SPACEWORKS_REDIS "$(redis_choice_word "$REDIS_CHOICE")"
  if [[ "$DATABASE_CHOICE" == 2 ]]; then
    local runtime_password mode=direct maintenance
    runtime_password="$(rand_key 32)"
    db_url_is_pooler "$EXTERNAL_DB_URL" && mode=session
    maintenance="$(normalize_postgres_scheme "${EXTERNAL_DB_DIRECT_URL:-$EXTERNAL_DB_URL}")"
    env_setting SPACEWORKS_MAINTENANCE_DATABASE_URL "$maintenance"
    env_setting SPACEWORKS_DATABASE_RUNTIME_URL \
      "$(derive_runtime_database_url "$EXTERNAL_DB_URL" "${POSTGRES_APP_USER:-spaceworks_app}" "$runtime_password")"
    env_setting DATABASE_CONNECTION_MODE "$mode"
    env_setting MANAGED_POSTGRES True
  fi
  if [[ "$REDIS_CHOICE" == 2 ]]; then
    env_setting CELERY_BROKER_URL "$(normalize_redis_url "$EXTERNAL_REDIS_URL")"
  fi
  if [[ "$STORAGE" == 2 ]]; then
    write_storage_capabilities_file
    env_setting STORAGE_CAPABILITIES_FILE /run/spaceworks-storage/capabilities.json
  fi
  if [[ "$EMAIL_CHOICE" == 2 ]]; then
    env_setting EMAIL_HOST "$SMTP_HOST"
    env_setting EMAIL_PORT "$SMTP_PORT"
    env_setting EMAIL_HOST_USER "$SMTP_USER"
    env_setting EMAIL_HOST_PASSWORD "$SMTP_PASSWORD"
    env_setting EMAIL_USE_TLS "$([[ "$SMTP_TLS" =~ ^[Yy] ]] && echo True || echo False)"
    env_setting DEFAULT_FROM_EMAIL "$SMTP_FROM"
  fi
}

# The strict version-1 file apps/storage_capabilities reads; it holds no credentials. It is mounted
# read-only from ./storage-config by docker/compose.external-storage.yml.
write_storage_capabilities_file() {
  local directory="$ROOT/storage-config" methods='["put"]' versioning=never_versioned history=false lock=false
  if [[ "$STORAGE_PROFILE" == full ]]; then
    methods='["post","put"]'; versioning=enabled; history=true; lock=null
    [[ "$PRESIGN_METHOD" == post ]] || methods='["put"]'
  fi
  mkdir -p "$directory"
  bucket_contract() {
    printf '{"endpoint":"%s","region":"%s","bucket":"%s","generation":1,"presign_methods":%s,"versioning":"%s",' \
      "$S3_ENDPOINT" "$S3_REGION" "$1" "$methods" "$versioning"
    printf '"staging_policy":"private","public_delivery":"%s","list_delete_versions":%s,"conditional_create":null,' "$2" "$history"
    printf '"copy":null,"multipart":null,"object_lock":%s,"cors_management":null}' "$lock"
  }
  printf '{"version":1,"buckets":{"private":%s,"public_image":%s}}\n' \
    "$(bucket_contract "$PRIVATE_BUCKET" private)" "$(bucket_contract "$IMAGE_BUCKET" public)" \
    > "$directory/capabilities.json"
  chmod 755 "$directory"; chmod 644 "$directory/capabilities.json"
  unset -f bucket_contract
}
