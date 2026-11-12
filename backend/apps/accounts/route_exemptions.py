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
event-check-in-station-badge event-check-in-station-badge-receipts
device-enrollment-challenge device-enrollment-complete device-heartbeat device-command-lease
device-command-ack device-printer-job-telemetry device-printer-job-result
device-label-command-content device-label-command-result kiosk-replay-prepare
kiosk-replay-execute kiosk-station-session metrics space-display-register space-display-state
integration-event-list integration-event-detail integration-event-participants
integration-booking-resource-list integration-booking-resource-detail
integration-booking-resource-reservations integration-booking-list integration-booking-detail
""".split())

PUBLIC_ROUTES = frozenset("""
website-discover website-discover-organizers handle-check public-legal-page public-config health readiness announcement-feed one-click-unsubscribe api-redoc-ui
""".split())

# Decision 335(d): the display screen's poll with its secret in the Authorization header (not the path).
NON_ACCOUNT_ROUTES |= {"space-display-state-header"}
# Release 2 L10: signed device-protocol routes of the (off-by-default) machine-integration foundation.
NON_ACCOUNT_ROUTES |= {"device-integration-queue", "device-integration-job-report"}
# Release 2 L3: Apple's pass web service, authenticated by the pass's own token (PassKit protocol).
NON_ACCOUNT_ROUTES |= {"wallet-apple-registration", "wallet-apple-serials", "wallet-apple-pass", "wallet-apple-log"}
# Decision 223: the guest pass .pkpass download; the signed one-minute link in the URL is the credential.
NON_ACCOUNT_ROUTES |= {"wallet-guest-pass-download"}
# Release 2 L6: signed server reads of ticket orders (`orders:read`).
NON_ACCOUNT_ROUTES |= {"integration-order-list", "integration-order-detail"}
# Release 2 L21a: signed server reads of application counts (`applications:read`).
NON_ACCOUNT_ROUTES |= {"integration-application-counts"}

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
# r2-superadmin-controls (#185, #187A): the public paused check and the platform's own
# hosting-invoice provider callbacks.
PUBLIC_ROUTES |= {"public-makerspace-availability"}
PROVIDER_ONLY_ROUTES |= {"managed-hosting-stripe-webhook", "managed-hosting-razorpay-webhook"}
# r2-control-restructure (#190): the one-use move-export download link (signed, five minutes).
NON_ACCOUNT_ROUTES |= {"selfhost-move-download"}
# Decision 310-312: the signed Device Adapter API v1 (device signature, not an account token).
NON_ACCOUNT_ROUTES |= {
    "device-adapter-hello", "device-adapter-bindings", "device-adapter-status", "device-adapter-events",
    "device-adapter-command-lease", "device-adapter-command-ack", "device-adapter-access",
    "device-adapter-session-start", "device-adapter-session-stop", "device-adapter-usage",
    "device-adapter-job-lease", "device-adapter-job-ack", "device-adapter-job-progress", "device-adapter-job-report",
    "device-adapter-job-file", "device-adapter-kiosk-start", "device-adapter-kiosk-end", "device-adapter-kiosk-scan",
    "device-adapter-kiosk-evidence", "device-adapter-kiosk-issue", "device-adapter-kiosk-return",
    "device-adapter-media-signal", "device-adapter-media-snapshot", "device-adapter-media-recording",
    "device-adapter-artifact-request", "device-adapter-artifact-complete", "device-adapter-access-cache",
    "device-adapter-offline-decisions", "device-adapter-config", "device-adapter-config-ack", "device-adapter-time"}
