"""Audit presentation entries for addressed messaging and canonical notification ingress.

Labels only: sender identities, phone/alias hashes, provider message IDs, receipt
payloads, consent sources, order IDs and secrets never become displayed metadata.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("messaging.alias_correlated", "Messaging recipient alias correlated"),
    P("messaging.consent_archived", "Messaging consent archived"),
    P("messaging.consent_recorded", "Messaging consent recorded"),
    P("messaging.correlation_reset", "Messaging correlation reset"),
    P("messaging.correlations_blocked", "Messaging correlations blocked"),
    P("messaging.probe_claimed", "Messaging delivery probe claimed"),
    P("messaging.probe_confirmed", "Messaging delivery probe confirmed"),
    P("messaging.probe_released", "Messaging delivery probe released"),
    P("messaging.recipient_suppressed", "Messaging recipient suppressed"),
    P("messaging.retired_credentials_wiped", "Retired messaging credentials wiped"),
    P("messaging.test_enqueued", "Messaging test queued"),
    P("notification.account_scrubbed", "Personal notification history scrubbed"),
    P("notification.delivery_observed", "Notification delivery status observed"),
    P("notification.webhook_received", "Notification provider receipt recorded"),
    P("payment.mobile_order_created", "Mobile payment order created"),
)
