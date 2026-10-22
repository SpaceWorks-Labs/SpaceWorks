"""Non-account protocols and public/member namespaces reviewed by the URL guard.

An exemption only skips the staff-registry check. It never admits an account token;
each protocol keeps its own authentication and account surfaces still fail closed.
"""

PROVIDER_ONLY_ROUTES = frozenset("""
free_tick:tick notification-media telegram-webhook email-provider-webhook email-bounce-webhook whatsapp-meta-webhook
whatsapp-twilio-inbound whatsapp-twilio-status notification-slack-oauth
notification-slack-inbound notification-mattermost-oauth notification-mattermost-inbound
notification-discord-oauth notification-discord-inbound stripe-connect-webhook
stripe-connect-callback stripe-webhook razorpay-webhook
messaging-twilio-platform-status messaging-twilio-platform-inbound
messaging-twilio-status messaging-twilio-inbound messaging-meta-platform messaging-meta
""".split())

NON_ACCOUNT_ROUTES = frozenset("""
backup-archive-download data-export-download internal-tls-check cron-return-reminders
event-check-in-station-session event-check-in-station-roster event-check-in-station-sync
device-enrollment-challenge device-enrollment-complete device-heartbeat device-command-lease
device-command-ack device-printer-job-telemetry device-printer-job-result
device-label-command-content device-label-command-result kiosk-replay-prepare
kiosk-replay-execute kiosk-station-session metrics
integration-event-list integration-event-detail integration-event-participants
integration-booking-resource-list integration-booking-resource-detail
integration-booking-resource-reservations integration-booking-list integration-booking-detail
""".split())

PUBLIC_ROUTES = frozenset("""
website-discover public-config health readiness announcement-feed one-click-unsubscribe api-redoc-ui
""".split())

NON_STAFF_ROUTES = PROVIDER_ONLY_ROUTES | NON_ACCOUNT_ROUTES | PUBLIC_ROUTES


def route_exemption(route, name):
    """Return the deliberate boundary, including routes outside the JSON API."""
    if not route.startswith("api/"):
        return "non-api (Django control permissions or public website)"
    if name in PROVIDER_ONLY_ROUTES:
        return "provider-only"
    # Mounted only under profile=free, inside the `free_tick` namespace; the URL
    # walk sees the bare leaf name, so match `free_tick:tick` by its exact path.
    if (route, name) == ("api/v1/internal/free/tick", "tick"):
        return "provider-only"
    if name in NON_ACCOUNT_ROUTES:
        return "independent capability or protocol"
    if name in PUBLIC_ROUTES:
        return "public"
    if name and route.startswith(("api/public/", "api/v1/public/")):
        return "public/member API (no staff account access)"
    if name and route.startswith(("api/v1/member/", "api/v1/memberships/")):
        return "member API (no staff account access)"
    return None
