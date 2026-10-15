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
  "add_header Content-Security-Policy \"frame-ancestors 'none'\" always;" >> "$headers"
if [ -z "$script$collect$domain" ]; then exit 0; fi
fail() { echo 'Invalid WEB_ANALYTICS configuration' >&2; exit 1; }
[ -n "$script" ] && [ -n "$collect" ] && [ -n "$domain" ] || fail
origin() {
  printf '%s' "$1" | grep -Eq '^https://[A-Za-z0-9.-]+(:[0-9]+)?(/[A-Za-z0-9._/-]*)?$' || fail
  printf '%s' "$1" | sed -E 's#^(https://[^/]+).*#\1#'
}
script_origin="$(origin "$script")"
collect_origin="$(origin "$collect")"
printf '%s' "$script" | grep -Eq '[./-]manual[.-]' || fail
printf '%s' "$domain" | grep -Eq '^[A-Za-z0-9.-]{1,253}$' || fail
extra_origins=''
for extra in ${WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS:-}; do
  validated="$(origin "$extra")"
  [ "$validated" = "$extra" ] || fail
  extra_origins="$extra_origins $validated"
done
# Opt-in deployments declare external API/object-storage origins here explicitly.
printf '%s\n' "add_header Content-Security-Policy \"script-src 'self' 'wasm-unsafe-eval' https://accounts.google.com https://appleid.cdn-apple.com $script_origin; connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com https://appleid.apple.com $collect_origin$extra_origins\" always;" >> "$headers"
cat >> "${TENANT_CONFIG_PATH:-/usr/share/nginx/html/config.js}" <<EOF
window.__WEB_ANALYTICS__ = {scriptUrl: "$script", collectUrl: "$collect", domain: "$domain"};
EOF
