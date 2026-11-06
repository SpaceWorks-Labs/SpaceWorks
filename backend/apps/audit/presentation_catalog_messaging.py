"""Audit presentation entries for addressed messaging and canonical notification ingress.

Labels only: sender identities, phone/alias hashes, provider message IDs, receipt
payloads, consent sources, order IDs and secrets never become displayed metadata.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("messaging.alias_correlated", gettext_lazy("Messaging recipient alias correlated")),
    P("messaging.consent_archived", gettext_lazy("Messaging consent archived")),
    P("messaging.consent_recorded", gettext_lazy("Messaging consent recorded")),
    P("messaging.correlation_reset", gettext_lazy("Messaging correlation reset")),
    P("messaging.correlations_blocked", gettext_lazy("Messaging correlations blocked")),
    P("messaging.probe_claimed", gettext_lazy("Messaging delivery probe claimed")),
    P("messaging.probe_confirmed", gettext_lazy("Messaging delivery probe confirmed")),
    P("messaging.probe_released", gettext_lazy("Messaging delivery probe released")),
    P("messaging.recipient_suppressed", gettext_lazy("Messaging recipient suppressed")),
    P("messaging.retired_credentials_wiped", gettext_lazy("Retired messaging credentials wiped")),
    P("messaging.test_enqueued", gettext_lazy("Messaging test queued")),
    P("notification.account_scrubbed", gettext_lazy("Personal notification history scrubbed")),
    P("notification.delivery_observed", gettext_lazy("Notification delivery status observed")),
    P("notification.webhook_received", gettext_lazy("Notification provider receipt recorded")),
    P("payment.mobile_order_created", gettext_lazy("Mobile payment order created")),
)
