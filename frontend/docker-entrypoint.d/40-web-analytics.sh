#!/bin/sh
set -eu
# Runs after runtime tenant config; configuration is opt-in and never interpolated unchecked.
script="${WEB_ANALYTICS_SCRIPT_URL:-}"
collect="${WEB_ANALYTICS_COLLECT_URL:-}"
domain="${WEB_ANALYTICS_DOMAIN:-}"
headers="${WEB_ANALYTICS_HEADERS_PATH:-/etc/nginx/analytics-headers.conf}"
printf '%s\n' 'add_header Referrer-Policy strict-origin always;' > "$headers"
# nginx stops inheriting server headers as soon as a location adds any header.
# Keep framing protection in the include used by every SPA/static location, even
# when analytics is disabled. Backend embeds intentionally do not include it.
printf '%s\n' 'add_header X-Frame-Options "DENY" always;' \
  'add_header X-Content-Type-Options "nosniff" always;' \
  "add_header Content-Security-Policy \"frame-ancestors 'none'\" always;" >> "$headers"
fail() { echo 'Invalid WEB_ANALYTICS configuration' >&2; exit 1; }
origin() {
  printf '%s' "$1" | grep -Eq '^https://[A-Za-z0-9.-]+(:[0-9]+)?(/[A-Za-z0-9._/-]*)?$' || fail
  printf '%s' "$1" | sed -E 's#^(https://[^/]+).*#\1#'
}
script_origin=''
collect_origin=''
if [ -n "$script$collect$domain" ]; then
  [ -n "$script" ] && [ -n "$collect" ] && [ -n "$domain" ] || fail
  script_origin="$(origin "$script")"
  collect_origin="$(origin "$collect")"
  printf '%s' "$script" | grep -Eq '[./-]manual[.-]' || fail
  printf '%s' "$domain" | grep -Eq '^[A-Za-z0-9.-]{1,253}$' || fail
fi
telemetry_origins=''
for extra in $(printf '%s' "${WEB_TELEMETRY_ALLOWED_ORIGINS:-}" | tr ',' ' '); do
  validated="$(origin "$extra")"
  [ "$validated" = "$extra" ] || fail
  telemetry_origins="$telemetry_origins $validated"
done
# Cloudflare Turnstile (sign-in CAPTCHA) is allowed only when the deployment configured it;
# its widget frame needs no frame-src entry because this policy sets no frame-src at all.
turnstile_origin=''
[ -z "${TURNSTILE_SITE_KEY:-}" ] || turnstile_origin=' https://challenges.cloudflare.com'
# Every deployment gets a script baseline, so an injected <script> has a CSP backstop even with
# analytics and telemetry off. index.html carries no inline script (boot code is /boot.js), so
# neither 'unsafe-inline' nor a hash is needed. connect-src stays unset here: API and object-storage
# origins vary per deployment and are declared only by the opt-in policy below.
script_sources="'self' 'wasm-unsafe-eval' https://accounts.google.com https://appleid.cdn-apple.com"
baseline="object-src 'none'; base-uri 'self'"
if [ -z "$script$collect$domain$telemetry_origins" ]; then
  printf '%s\n' "add_header Content-Security-Policy \"script-src $script_sources$turnstile_origin; $baseline\" always;" >> "$headers"
  exit 0
fi
extra_origins=''
for extra in ${WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS:-}; do
  validated="$(origin "$extra")"
  [ "$validated" = "$extra" ] || fail
  extra_origins="$extra_origins $validated"
done
# Opt-in deployments declare external API/object-storage origins here explicitly.
printf '%s\n' "add_header Content-Security-Policy \"script-src $script_sources $script_origin$telemetry_origins$turnstile_origin; connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com https://appleid.apple.com $collect_origin$extra_origins$telemetry_origins$turnstile_origin; $baseline\" always;" >> "$headers"
if [ -n "$script" ]; then
cat >> "${TENANT_CONFIG_PATH:-/usr/share/nginx/html/config.js}" <<EOF
window.__WEB_ANALYTICS__ = {scriptUrl: "$script", collectUrl: "$collect", domain: "$domain"};
EOF
fi
