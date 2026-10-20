#!/usr/bin/env bash
# No filesystem or Docker effects: gather every deployment choice, then confirm once.
source "$(dirname "${BASH_SOURCE[0]}")/setup-question-input.sh"
source "$(dirname "${BASH_SOURCE[0]}")/setup-area-questions.sh"
source "$(dirname "${BASH_SOURCE[0]}")/installer/answers.sh"
source "$(dirname "${BASH_SOURCE[0]}")/installer/setup-scan.sh"

ask_setup_questions() {
  CONTROL_PLANE_PROXY=false; CONTROL_PLANE_ALLOW_CIDRS=''; CONTROL_PLANE_TUNNEL_PORT=''
  if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 ]]; then exec 3</dev/null; else exec 3</dev/tty; fi
  echo 'SpaceWorks deployment questions. Enter accepts the [default].'
  # The free profile is opt-in: --profile free / SPACEWORKS_DEPLOYMENT_PROFILE=free, or
  # option 4 below in an interactive run. It adds no question to the full path.
  local free_status=0 hosting_choices=1,2,3
  if [[ "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" == free ]]; then
    confirm_free_profile || free_status=$?
    exec 3<&-
    return "$free_status"
  fi
  echo 'Hosting model:'
  echo '  1) One makerspace on this server - one community, at /m/<slug>.'
  echo '  2) Several makerspaces - shared server, each at /m/<slug>; the superadmin adds more later.'
  echo '  3) Hosted platform - each makerspace has a subdomain of your platform domain.'
  if [[ "${SETUP_NON_INTERACTIVE:-0}" != 1 && -z "${SPACEWORKS_DEPLOYMENT_PROFILE:-}" ]]; then
    echo '  4) Free profile (opt-in) - one web process, no worker or scheduler; external services and an HTTP tick.'
    hosting_choices=1,2,3,4
  fi
  question HOSTING_MODEL 'Hosting model' 1 "choices:$hosting_choices" || return 1
  if [[ "$HOSTING_MODEL" == 4 ]]; then
    SPACEWORKS_DEPLOYMENT_PROFILE=free
    export SPACEWORKS_DEPLOYMENT_PROFILE
    HOSTING_MODEL=''
    confirm_free_profile || free_status=$?
    exec 3<&-
    return "$free_status"
  fi
  PLATFORM_DOMAIN=''; PUBLIC_DOMAIN=''; TLS_EMAIL=''; SITE_ORIGINS=''
  if [[ "$HOSTING_MODEL" == 3 ]]; then
    question PLATFORM_DOMAIN 'Platform domain' '' domain || return 1
  fi
  echo 'Run the website (web frontend) on this server?'
  echo '  1) Yes - serve the website here.'
  echo '  2) No, API only - website hosted elsewhere (Netlify etc.).'
  question RUN_FRONTEND 'Website' 1 choices:1,2 || return 1
  if [[ "$RUN_FRONTEND" == 2 ]]; then
    question SITE_ORIGINS 'Site URL(s), comma-separated HTTPS origins (first is the staff site)' '' origins || return 1
  fi
  if [[ "$HOSTING_MODEL" == 3 ]]; then
    echo 'Hosted platforms require automatic HTTPS through the SaaS Caddy edge.'
    HTTPS_MODE=2
    question TLS_EMAIL 'HTTPS certificate email' '' email || return 1
  else
    echo 'HTTPS:'
    [[ "$RUN_FRONTEND" == 2 ]] || echo '  1) None - plain HTTP on localhost only (local trial).'
    echo '  2) Automatic HTTPS - built-in Caddy; point DNS at this server.'
    echo '  3) I already run a reverse proxy - forward HTTPS to this server.'
    # API-only with an external website requires HTTPS, so plain HTTP is not offered.
    if [[ "$RUN_FRONTEND" == 2 ]]; then
      question HTTPS_MODE 'HTTPS' 2 choices:2,3 || return 1
    else
      question HTTPS_MODE 'HTTPS' 1 choices:1,2,3 || return 1
    fi
    if [[ "$HTTPS_MODE" != 1 ]]; then
      question PUBLIC_DOMAIN 'Public API/server domain' '' domain || return 1
      [[ "$HTTPS_MODE" != 2 ]] || question TLS_EMAIL 'HTTPS certificate email' '' email || return 1
    fi
  fi
  echo 'File storage:'
  echo '  1) Bundled Silo object storage - private evidence and public images on this server.'
  echo '  2) External S3-compatible buckets - provision buckets, versioning, privacy and CORS yourself.'
  question STORAGE 'File storage' 1 choices:1,2 || return 1
  S3_ENDPOINT=''; S3_REGION=us-east-1; PRIVATE_BUCKET=evidence; IMAGE_BUCKET=public-images
  S3_ACCESS_KEY=''; S3_SECRET_KEY=''; IMAGE_BASE_URL=''; PRESIGN_METHOD=post
  if [[ "$STORAGE" == 2 ]]; then
    local storage_url_rule=url
    [[ "$HTTPS_MODE" == 1 ]] || storage_url_rule=secure_url
    question S3_ENDPOINT 'S3 endpoint (also browser reachable)' '' "$storage_url_rule" || return 1
    question S3_REGION 'S3 region' us-east-1 region || return 1
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
    question IMAGE_BASE_URL 'Public image base URL (includes bucket/path)' '' "$storage_url_rule" || return 1
    question PRESIGN_METHOD 'Presign method' post choices:put,post || return 1
  fi
  if [[ "$HOSTING_MODEL" != 3 && ! ( "$RUN_FRONTEND" == 2 && "$HTTPS_MODE" == 3 ) ]]; then
    echo 'The Django control plane is for superadmin operations; website access is off by default.'
    if [[ "$HTTPS_MODE" == 1 ]]; then
      echo 'Plain HTTP is restricted to this computer; use HTTPS for LAN access.'
    fi
    local CP_ANSWER
    question CP_ANSWER 'Reach the Django control plane (/control/) through the website?' N choices:Y,y,yes,YES,N,n,no,NO || return 1
    [[ ! "$CP_ANSWER" =~ ^[Yy] ]] || CONTROL_PLANE_PROXY=true
    if [[ "$CONTROL_PLANE_PROXY" == true && "$HTTPS_MODE" != 3 ]]; then
      question CONTROL_PLANE_ALLOW_CIDRS 'Allowed client IPs/CIDRs, space-separated (blank = any)' '' cidrs || return 1
    fi
    if [[ "$HTTPS_MODE" == 2 ]]; then
      while true; do
        question CONTROL_PLANE_TUNNEL_PORT 'Loopback port for an SSH-tunnel fallback (blank = off)' '' port || return 1
        case "$CONTROL_PLANE_TUNNEL_PORT" in
          80|443|9000|9001) echo 'That port is reserved for the website or bundled storage. Choose another port.' ;;
          *) break ;;
        esac
      done
    fi
  fi
  WEBHOST="$PUBLIC_DOMAIN"
  if [[ "$HOSTING_MODEL" == 3 ]]; then WEBHOST="$PLATFORM_DOMAIN"; fi
  local webhost_rule=host
  [[ "$HTTPS_MODE" != 1 ]] || webhost_rule=loopback
  [[ -n "$WEBHOST" ]] || question WEBHOST 'Web address (host name or IP, no http://)' localhost "$webhost_rule" || return 1
  echo 'Makerspaces belong to an organization (your network, university, company or community).'
  question ORG_NAME 'Organization name' '' org_name || return 1
  question MSNAME 'Name of your makerspace' 'My Makerspace' name || return 1
  [[ "$HOSTING_MODEL" != 3 ]] || question MS_SUBDOMAIN 'First makerspace subdomain' makerspace slug || return 1
  question SETUP_MFA_ENABLED 'Turn on two-step sign-in (authenticator app)?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
  question SETUP_SOCIAL_PROVIDERS 'Which sign-in options besides email + password? Google, Apple, GitHub — comma list, or none' google providers || return 1
  ask_setup_areas || return 1
  ask_setup_scanner || return $?
  question ADMINUSER 'Admin login username' admin username || return 1
  question ADMINEMAIL 'Admin email' '' email || return 1
  question ADMINPASS 'Admin password (blank generates one)' '' secret || return 1
  GEN_PASS=0
  if [[ -z "$ADMINPASS" ]]; then ADMINPASS="$(rand_key 24)"; GEN_PASS=1; fi
  STRIPE_SECRET_KEY=''; STRIPE_WEBHOOK_SECRET=''; STRIPE_DEFAULT_CURRENCY="${AREA_root_currency:-usd}"
  if [[ ",${SETUP_SELECTED_AREAS}," == *,payments,* ]]; then
    while true; do
      question STRIPE_SECRET_KEY 'Stripe secret key' '' secret || return 1
      question STRIPE_WEBHOOK_SECRET 'Stripe webhook secret' '' secret || return 1
      [[ -z "$STRIPE_SECRET_KEY" && -z "$STRIPE_WEBHOOK_SECRET" || -n "$STRIPE_SECRET_KEY" && -n "$STRIPE_WEBHOOK_SECRET" ]] && break
      echo 'Stripe requires both secrets. Enter both or skip both.'
    done
  fi
  if [[ "${SPACEWORKS_INSTALL_REPOSITORY_PINNED:-0}" == 1 ]]; then
    echo "GitHub repository to follow [$SPACEWORKS_REPOSITORY] (selected before download)."
  else
    question SPACEWORKS_REPOSITORY 'GitHub repository to follow' "${SPACEWORKS_REPOSITORY:-SpaceWorks-HQ/SpaceWorks}" repository || return 1
  fi
  INSTALL_RUNNER=N
  if [[ "$(uname -s)" == Linux ]] && command -v systemctl >/dev/null 2>&1 \
    && [[ -d /run/systemd/system ]]; then
    echo 'Pair the runner with the required GitHub approval and repository settings after installation.'
    question INSTALL_RUNNER 'Install a GitHub Actions runner on this server for automatic deploys?' N choices:Y,y,yes,YES,N,n,no,NO || return 1
  else
    echo 'GitHub Actions runner installation supports only Linux with running systemd; skipping.'
  fi
  setup_summary
  local proceed
  question proceed 'Proceed?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
  exec 3<&-
  [[ "$proceed" =~ ^[Yy] ]] || { echo 'Cancelled; nothing was installed or configured.'; return 130; }
  check_unused_answers || return $?
  ANSWERS_CONFIRMED=yes
}

confirm_free_profile() {
  free_profile_notice
  echo '  Will perform: write a private free-profile .env with generated secrets. No services start.'
  [[ "${SETUP_NON_INTERACTIVE:-0}" != 1 ]] || return 0
  local proceed
  question proceed 'Prepare the free profile?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
  [[ "$proceed" =~ ^[Yy] ]] || { echo 'Cancelled; nothing was installed or configured.'; return 130; }
}

free_profile_notice() {
  echo
  echo 'Free profile (opt-in, best effort)'
  echo '  One 512 MB web container and one process: no worker, scheduler, Redis or live-events process.'
  echo '  Malware scanning is off: uploads are validated by type and size but not scanned.'
  echo '  Scheduled work runs only when an external cron calls POST /api/v1/internal/free/tick'
  echo '  over HTTPS with the X-Cron-Secret header (FREE_TICK_SECRET in the private .env).'
  echo '  It needs an external PostgreSQL, S3-compatible storage and an email provider, and has no'
  echo '  scheduled pg_dump; see docs/deploy/cloud-free.md before relying on it.'
}

setup_summary() {
  echo
  echo 'Deployment summary'
  local hosting website https storage
  case "$HOSTING_MODEL" in 1) hosting='one makerspace' ;; 2) hosting='several makerspaces at /m/<slug>' ;; 3) hosting='hosted platform with tenant subdomains' ;; esac
  [[ "$RUN_FRONTEND" == 1 ]] && website=yes || website='API only, website elsewhere'
  case "$HTTPS_MODE" in 1) https='plain HTTP' ;; 2) https='automatic Caddy HTTPS' ;; 3) https='existing reverse proxy' ;; esac
  [[ "$STORAGE" == 1 ]] && storage='bundled Silo' || storage='external S3'
  printf '  Hosting model: %s; website: %s; HTTPS: %s; storage: %s\n' \
    "$hosting" "$website" "$https" "$storage"
  printf '  Server: %s; platform: %s; certificate email: %s; external sites: %s\n' \
    "$WEBHOST" "${PLATFORM_DOMAIN:-none}" "${TLS_EMAIL:-none}" "${SITE_ORIGINS:-none}"
  local control_plane=off tunnel=off scheme=https
  [[ "$HTTPS_MODE" != 1 ]] || scheme=http
  [[ "${CONTROL_PLANE_PROXY:-false}" != true ]] || control_plane="$scheme://$WEBHOST/control/ (allowed: ${CONTROL_PLANE_ALLOW_CIDRS:-any})"
  [[ -z "${CONTROL_PLANE_TUNNEL_PORT:-}" ]] || tunnel="127.0.0.1:$CONTROL_PLANE_TUNNEL_PORT"
  printf '  Control plane: %s ; SSH tunnel: %s\n' "$control_plane" "$tunnel"
  printf '  Makerspace: %s; URL slug/subdomain: %s; edition: %s; request access: %s\n' \
    "$MSNAME" "${MS_SUBDOMAIN:-none}" "$SPACEWORKS_EDITION" "$([[ ",${SETUP_SELECTED_AREAS}," == *,inventory,* ]] && echo "$REQUEST_ACCESS" || echo 'lending disabled')"
  printf '  Organization: %s (owner of %s)\n' "$ORG_NAME" "$MSNAME"
  setup_areas_summary
  printf '  File scanning: %s\n' "${SETUP_SCAN_MODE:-none}"
  printf '  Admin: %s <%s>; password: %s (hidden)\n' "$ADMINUSER" "$ADMINEMAIL" "$([[ "$GEN_PASS" == 1 ]] && echo generated || echo entered)"
  printf '  Two-step sign-in: %s; sign-in providers: %s (keys configured later in the console)\n' \
    "$SETUP_MFA_ENABLED" "$SETUP_SOCIAL_PROVIDERS"
  printf '  Stripe: %s; currency: %s; install GitHub Actions runner: %s\n' \
    "$([[ -n "$STRIPE_SECRET_KEY" ]] && echo 'configured (secrets hidden)' || echo skipped)" "$STRIPE_DEFAULT_CURRENCY" "$INSTALL_RUNNER"
  if [[ "$STORAGE" == 2 ]]; then
    printf '  S3: %s; region: %s; private bucket: %s; public bucket: %s\n' "$S3_ENDPOINT" "$S3_REGION" "$PRIVATE_BUCKET" "$IMAGE_BUCKET"
    printf '  Images: %s; presign: %s; access/secret keys: entered (hidden)\n' "$IMAGE_BASE_URL" "$PRESIGN_METHOD"
  fi
  echo "  GitHub repository: $SPACEWORKS_REPOSITORY"
  echo "  migrate builds the database tables. It runs once and stops. It's required."
  echo "  orchestration is a start-up safety check. It runs once and stops. It's required."
  local services='database, Redis'
  [[ "$STORAGE" != 1 ]] || services+=', Silo storage (bucket initializer)'
  services+=', API, live events, worker, scheduler'
  [[ "$RUN_FRONTEND" == 2 ]] && services+=', API edge' || services+=', website'
  [[ "$HTTPS_MODE" != 2 ]] || services+=', Caddy HTTPS edge'
  echo "  Will run: $services; one-shot database/orchestration initialization and migrations."
  if [[ "$HOSTING_MODEL" == 3 ]]; then
    echo "  API origin: https://$MS_SUBDOMAIN.$PLATFORM_DOMAIN (also https://$PLATFORM_DOMAIN)."
    echo "  DNS: point the platform apex, origin and tenant subdomains at this server."
  elif [[ "$HTTPS_MODE" != 1 ]]; then
    echo "  API origin: https://$WEBHOST. Point its DNS at this server/proxy."
  fi
  if [[ "$STORAGE" == 1 && "$HTTPS_MODE" != 1 ]]; then
    echo "  Storage DNS: files.${PLATFORM_DOMAIN:-$WEBHOST} must point at this server/proxy."
    [[ "$HTTPS_MODE" != 3 ]] || echo "  Existing proxy must forward files.$WEBHOST to 127.0.0.1:9000 and the API/site to 127.0.0.1:8080, preserving Host and X-Forwarded-Proto: https."
  fi
  if [[ "$HTTPS_MODE" == 3 ]]; then
    echo '  Setup will write spaceworks-proxy.nginx.conf with these routes and print the nginx steps.'
  fi
  echo "  Will perform: ${SETUP_HOST_PLAN:-write private .env and topology, pull/build images, create your admin and makerspace, apply selected modules, start services and install the optional GitHub Actions runner}."
  echo '  Production contains no demo or example data. Secrets are saved privately, never printed here.'
}
