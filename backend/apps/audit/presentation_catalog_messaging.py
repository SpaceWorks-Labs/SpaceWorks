"""Audit presentation entries for addressed messaging and canonical notification ingress.

Labels only: sender identities, phone/alias hashes, provider message IDs, receipt
payloads, consent sources, order IDs and secrets never become displayed metadata.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("messaging.alias_correlated", gettext_noop("Messaging recipient alias correlated")),
    P("messaging.consent_archived", gettext_noop("Messaging consent archived")),
    P("messaging.consent_recorded", gettext_noop("Messaging consent recorded")),
    P("messaging.correlation_reset", gettext_noop("Messaging correlation reset")),
    P("messaging.correlations_blocked", gettext_noop("Messaging correlations blocked")),
    P("messaging.probe_claimed", gettext_noop("Messaging delivery probe claimed")),
    P("messaging.probe_confirmed", gettext_noop("Messaging delivery probe confirmed")),
    P("messaging.probe_released", gettext_noop("Messaging delivery probe released")),
    P("messaging.recipient_suppressed", gettext_noop("Messaging recipient suppressed")),
    P("messaging.retired_credentials_wiped", gettext_noop("Retired messaging credentials wiped")),
    P("messaging.test_enqueued", gettext_noop("Messaging test queued")),
    P("notification.account_scrubbed", gettext_noop("Personal notification history scrubbed")),
    P("notification.delivery_observed", gettext_noop("Notification delivery status observed")),
    P("notification.webhook_received", gettext_noop("Notification provider receipt recorded")),
    P("payment.mobile_order_created", gettext_noop("Mobile payment order created")),
)
