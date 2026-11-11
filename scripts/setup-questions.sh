#!/usr/bin/env bash
# No filesystem or Docker effects: gather every deployment choice, then confirm once.
source "$(dirname "${BASH_SOURCE[0]}")/setup-question-input.sh"
source "$(dirname "${BASH_SOURCE[0]}")/setup-area-questions.sh"
source "$(dirname "${BASH_SOURCE[0]}")/installer/answers.sh"
source "$(dirname "${BASH_SOURCE[0]}")/installer/setup-scan.sh"
source "$(dirname "${BASH_SOURCE[0]}")/installer/frontend-choice.sh"
source "$(dirname "${BASH_SOURCE[0]}")/installer/outside-services.sh"

ask_setup_questions() {
  CONTROL_PLANE_PROXY=false; CONTROL_PLANE_ALLOW_CIDRS=''; CONTROL_PLANE_TUNNEL_PORT=''
  if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 ]]; then exec 3</dev/null; else exec 3</dev/tty; fi
  echo 'SpaceWorks setup questions. Press Enter to accept the answer in [brackets].'
  # The free profile is opt-in: --profile free / SPACEWORKS_DEPLOYMENT_PROFILE=free, or
  # option 4 below in an interactive run. It adds no question to the full path.
  local free_status=0 hosting_choices=1,2,3
  if [[ "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" == free ]]; then
    confirm_free_profile || free_status=$?
    exec 3<&-
    return "$free_status"
  fi
  # Quick setup (decision 235) is interactive only: an answers file always takes the full path.
  SETUP_QUICK=N
  if [[ "${SETUP_NON_INTERACTIVE:-0}" != 1 ]]; then
    echo 'Quick setup asks only what it must and uses the recommended answer for the rest:'
    echo '  one makerspace on this server, built-in file storage, an admin password made for you.'
    echo '  Everything can be changed later in Settings. Answer n to choose each option yourself.'
    question SETUP_QUICK 'Use quick setup?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
    area_yes "$SETUP_QUICK" && SETUP_QUICK=Y || SETUP_QUICK=N
  fi
  if [[ "$SETUP_QUICK" == Y ]]; then
    ask_quick_setup_questions || return $?
    return 0
  fi
  echo 'Hosting model:'
  echo '  1) One makerspace on this server - one community, at /m/<slug>.'
  echo '  2) Several makerspaces - shared server, each at /m/<slug>; the superadmin adds more later.'
  echo '  3) Hosting other makerspaces - each makerspace gets a subdomain of your domain.'
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
  local frontend_status=0
  frontend_preset || frontend_status=$?
  if [[ "$frontend_status" == 0 ]]; then
    echo "Frontend: $(frontend_mode_label "$RUN_FRONTEND") (preset by --frontend)."
  elif [[ "$frontend_status" == 1 ]]; then
    echo 'What should this server run?'
    echo '  1) Full - the web app and the API.'
    echo '  2) API-only - the backend for mobile apps and integrations; no web app on this server.'
    question RUN_FRONTEND 'Frontend' 1 choices:1,2 || return 1
  else
    return "$frontend_status"
  fi
  if [[ "$RUN_FRONTEND" == 2 ]]; then
    echo 'Hosting the website elsewhere (Netlify etc.)? Enter its address so sign-in and email links open it.'
    echo 'Leave it blank when there is no website: links then point at this server, which answers only the API.'
    question SITE_ORIGINS 'Website URL(s), comma-separated HTTPS origins (first is the staff site; blank = none)' '' origins || return 1
  fi
  if [[ "$HOSTING_MODEL" == 3 ]]; then
    echo 'Hosting other makerspaces on subdomains requires automatic HTTPS (the built-in Caddy edge).'
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
  ask_outside_services || return 1
  if [[ "$HOSTING_MODEL" != 3 && ! ( "$RUN_FRONTEND" == 2 && "$HTTPS_MODE" == 3 ) ]]; then
    echo 'The control panel (/control/) is the platform administrator'"'"'s back office; reaching it from the website is off by default.'
    if [[ "$HTTPS_MODE" == 1 ]]; then
      echo 'Plain HTTP is restricted to this computer; use HTTPS for LAN access.'
    fi
    local CP_ANSWER
    question CP_ANSWER 'Reach the control panel (/control/) through the website?' N choices:Y,y,yes,YES,N,n,no,NO || return 1
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
  echo 'Staff always need two-step sign-in (an authenticator app or a passkey); this answer is for members.'
  question SETUP_MFA_ENABLED 'Let members turn on two-step sign-in too?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
  question SETUP_SOCIAL_PROVIDERS 'Which sign-in options besides email + password? Google, Apple, GitHub — comma list, or none' google providers || return 1
  ask_setup_landing || return 1
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
    question SPACEWORKS_REPOSITORY 'GitHub repository to follow' "${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}" repository || return 1
  fi
  INSTALL_RUNNER=N
  if [[ "$(uname -s)" == Linux ]] && command -v systemctl >/dev/null 2>&1 \
    && [[ -d /run/systemd/system ]]; then
    echo 'Pair the runner with the required GitHub approval and repository settings after installation.'
    question INSTALL_RUNNER 'Install a GitHub Actions runner on this server for automatic deploys?' N choices:Y,y,yes,YES,N,n,no,NO || return 1
  else
    echo 'GitHub Actions runner installation supports only Linux with running systemd; skipping.'
  fi
  confirm_setup_answers
}

confirm_setup_answers() {
  setup_summary
  local proceed
  question proceed 'Proceed?' Y choices:Y,y,yes,YES,N,n,no,NO || return 1
  exec 3<&-
  [[ "$proceed" =~ ^[Yy] ]] || { echo 'Cancelled; nothing was installed or configured.'; return 130; }
  check_unused_answers || return $?
  ANSWERS_CONFIRMED=yes
}

# Quick setup (decision 235): the fewest questions, recommended answers for the rest. It
# writes the same answer keys as the full questionnaire, so setup.sh treats both alike.
ask_quick_setup_questions() {
  HOSTING_MODEL=1; STORAGE=1; PLATFORM_DOMAIN=''; PUBLIC_DOMAIN=''; TLS_EMAIL=''; SITE_ORIGINS=''
  S3_ENDPOINT=''; S3_REGION=us-east-1; PRIVATE_BUCKET=evidence; IMAGE_BUCKET=public-images
  S3_ACCESS_KEY=''; S3_SECRET_KEY=''; IMAGE_BASE_URL=''; PRESIGN_METHOD=post
  DATABASE_CHOICE=1; REDIS_CHOICE=1; EMAIL_CHOICE=1; STORAGE_PROFILE=limited; S3_PUBLIC_ENDPOINT=''
  local frontend_status=0
  frontend_preset || frontend_status=$?
  if [[ "$frontend_status" == 0 ]]; then
    echo "Frontend: $(frontend_mode_label "$RUN_FRONTEND") (preset by --frontend)."
  elif [[ "$frontend_status" == 1 ]]; then
    echo 'What should this server run? 1) the web app and the API (most people), 2) the API only, for mobile apps.'
    question RUN_FRONTEND 'Web app and API (1) or API only (2)' 1 choices:1,2 || return 1
  else
    return "$frontend_status"
  fi
  if [[ "$RUN_FRONTEND" == 2 ]]; then
    echo 'An API-only server needs a domain name with HTTPS, for example api.example.org.'
    HTTPS_MODE=2
    question PUBLIC_DOMAIN 'Domain name of this server' '' domain || return 1
    echo 'If your website is hosted elsewhere, enter its address so sign-in and email links open it.'
    question SITE_ORIGINS 'Website address, https://... (blank = none)' '' origins || return 1
    WEBHOST="$PUBLIC_DOMAIN"
  else
    echo 'Give the domain name people will type, for example tools.example.org, and HTTPS is set up for you.'
    echo 'Press Enter to try SpaceWorks on this computer only (plain HTTP on localhost).'
    question WEBHOST 'Web address' localhost web_address || return 1
    if [[ "$WEBHOST" == localhost || "$WEBHOST" == 127.0.0.1 ]]; then HTTPS_MODE=1
    else HTTPS_MODE=2; PUBLIC_DOMAIN="$WEBHOST"; fi
  fi
  question MSNAME 'Name of your makerspace' 'My Makerspace' name || return 1
  ORG_NAME="$MSNAME"
  SETUP_MFA_ENABLED=Y; SETUP_SOCIAL_PROVIDERS=google; SETUP_HUB_LANDING=Y
  echo 'Now choose what your space runs. Each area can be switched on or off later in Settings.'
  ask_setup_areas || return 1
  ask_setup_scanner || return $?
  ADMINUSER='admin'
  echo 'Your admin account signs in with this email; a strong password is made for you and saved privately.'
  question ADMINEMAIL 'Your email address' '' email || return 1
  ADMINPASS="$(rand_key 24)"; GEN_PASS=1
  [[ "$HTTPS_MODE" != 2 ]] || TLS_EMAIL="$ADMINEMAIL"
  STRIPE_SECRET_KEY=''; STRIPE_WEBHOOK_SECRET=''; STRIPE_DEFAULT_CURRENCY="${AREA_root_currency:-usd}"
  [[ ",${SETUP_SELECTED_AREAS}," != *,payments,* ]] \
    || echo 'Online payments: add your Stripe keys later in Settings > Payments & billing.'
  SPACEWORKS_REPOSITORY="${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}"
  INSTALL_RUNNER=N
  confirm_setup_answers
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
  case "$HOSTING_MODEL" in 1) hosting='one makerspace' ;; 2) hosting='several makerspaces at /m/<slug>' ;; 3) hosting='hosting other makerspaces on subdomains' ;; esac
  website="$(frontend_mode_label "$RUN_FRONTEND")"
  [[ "$RUN_FRONTEND" == 1 ]] || website+="$([[ -n "$SITE_ORIGINS" ]] && echo ', website elsewhere' || echo ', no website')"
  case "$HTTPS_MODE" in 1) https='plain HTTP' ;; 2) https='automatic Caddy HTTPS' ;; 3) https='existing reverse proxy' ;; esac
  [[ "$STORAGE" == 1 ]] && storage='bundled Silo' || storage='external S3'
  printf '  Hosting model: %s; install: %s; HTTPS: %s; storage: %s\n' \
    "$hosting" "$website" "$https" "$storage"
  if [[ "$RUN_FRONTEND" == 2 && -z "$SITE_ORIGINS" && "$HOSTING_MODEL" != 3 ]]; then
    echo '  Links in emails point at this server until you set PUBLIC_APP_BASE_URL in .env to your website or app-link domain.'
  fi
  printf '  Server: %s; platform: %s; certificate email: %s; external sites: %s\n' \
    "$WEBHOST" "${PLATFORM_DOMAIN:-none}" "${TLS_EMAIL:-none}" "${SITE_ORIGINS:-none}"
  local control_plane=off tunnel=off scheme=https
  [[ "$HTTPS_MODE" != 1 ]] || scheme=http
  [[ "${CONTROL_PLANE_PROXY:-false}" != true ]] || control_plane="$scheme://$WEBHOST/control/ (allowed: ${CONTROL_PLANE_ALLOW_CIDRS:-any})"
  [[ -z "${CONTROL_PLANE_TUNNEL_PORT:-}" ]] || tunnel="127.0.0.1:$CONTROL_PLANE_TUNNEL_PORT"
  printf '  Control panel (/control/): %s ; SSH tunnel: %s\n' "$control_plane" "$tunnel"
  printf '  Makerspace: %s; URL slug/subdomain: %s; edition: %s; request access: %s\n' \
    "$MSNAME" "${MS_SUBDOMAIN:-none}" "$SPACEWORKS_EDITION" "$([[ ",${SETUP_SELECTED_AREAS}," == *,inventory,* ]] && echo "$REQUEST_ACCESS" || echo 'inventory off')"
  printf '  Organization: %s (owner of %s)\n' "$ORG_NAME" "$MSNAME"
  setup_areas_summary
  printf '  File scanning: %s\n' "${SETUP_SCAN_MODE:-none}"
  printf '  Admin: %s <%s>; password: %s (hidden)\n' "$ADMINUSER" "$ADMINEMAIL" "$([[ "$GEN_PASS" == 1 ]] && echo generated || echo entered)"
  printf '  Two-step sign-in: %s; sign-in providers: %s (keys configured later in the console); product page at /: %s\n' \
    "$SETUP_MFA_ENABLED" "$SETUP_SOCIAL_PROVIDERS" "$([[ "${SETUP_HUB_LANDING:-Y}" =~ ^[Yy] ]] && echo shown || echo hidden)"
  printf '  Stripe: %s; currency: %s; install GitHub Actions runner: %s\n' \
    "$([[ -n "$STRIPE_SECRET_KEY" ]] && echo 'configured (secrets hidden)' || echo skipped)" "$STRIPE_DEFAULT_CURRENCY" "$INSTALL_RUNNER"
  if [[ "$STORAGE" == 2 ]]; then
    printf '  S3: %s; region: %s; private bucket: %s; public bucket: %s\n' "$S3_ENDPOINT" "$S3_REGION" "$PRIVATE_BUCKET" "$IMAGE_BUCKET"
    printf '  Images: %s; presign: %s; access/secret keys: entered (hidden)\n' "$IMAGE_BASE_URL" "$PRESIGN_METHOD"
  fi
  outside_summary
  echo "  GitHub repository: $SPACEWORKS_REPOSITORY"
  echo "  migrate builds the database tables. It runs once and stops. It's required."
  echo "  orchestration is a start-up safety check. It runs once and stops. It's required."
  local services=''
  [[ "${DATABASE_CHOICE:-1}" == 2 ]] || services+='database, '
  [[ "${REDIS_CHOICE:-1}" == 2 ]] || services+='Redis, '
  [[ "$STORAGE" != 1 ]] || services+='Silo storage (bucket initializer), '
  services+='API, live events, worker, scheduler'
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
