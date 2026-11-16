"""Per-campaign delivery tallies from the delivery ledger; counts only, never recipients.

A recipient is counted once, by the best outcome across the campaign's email pipeline row
and every channel of their personal envelope: delivered beats waiting beats failed beats
skipped. The email-pipeline reservation marker is bookkeeping, not an outcome.
"""

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.events.broadcast_channels import EMAIL_RESERVATION
from apps.events.models_broadcasts import EventBroadcastDelivery

RANK = {"delivered": 3, "waiting": 2, "failed": 1, "skipped": 0}
LEGACY = {"sent": "delivered", "pending": "waiting", "failed": "failed", "skipped": "skipped"}
PERSONAL = {"accepted": "delivered", "sent": "delivered", "delivered": "delivered", "read": "delivered",
            "retrying": "waiting", "held": "waiting", "failed": "failed", "skipped": "skipped"}


def tallies(campaign):
    outcome = {}

    def note(recipient_id, value):
        if RANK[value] > RANK.get(outcome.get(recipient_id), -1):
            outcome[recipient_id] = value

    for recipient_id, status in EventBroadcastDelivery.objects.filter(campaign=campaign).values_list(
            "recipient_id", "status"):
        note(recipient_id, LEGACY.get(status, "waiting"))
    envelopes = NotificationEnvelope.objects.filter(
        makerspace_id=campaign.makerspace_id, source_kind="events.broadcast", source_id=str(campaign.pk))
    for recipient_id in envelopes.values_list("recipient_id", flat=True):
        # An envelope without a delivery row yet is still on its way.
        outcome.setdefault(recipient_id, "waiting")
    rows = NotificationDelivery.objects.filter(envelope__in=envelopes).exclude(
        state="skipped", last_error=EMAIL_RESERVATION).values_list("envelope__recipient_id", "state")
    for recipient_id, state in rows:
        note(recipient_id, PERSONAL.get(state, "waiting"))
    counts = {key: 0 for key in RANK}
    for value in outcome.values():
        counts[value] += 1
    return {"campaign_id": campaign.pk, "status": campaign.status, "total": len(outcome), **counts}
