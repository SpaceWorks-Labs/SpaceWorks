"""Event ID-card reconcile sweep (release 2 L3): issue to new confirmed registrants and
revoke cards whose registration ended, for events with a published card design."""
import logging

from celery import shared_task

from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)


@shared_task
def reconcile_event_id_cards_task(limit=50):
    from .id_cards import reconcile_due, reconcile_event
    done = 0
    for event_id in bounded.items(reconcile_due(limit=bounded.rows(limit))):
        try:
            reconcile_event(event_id)
            done += 1
        except Exception:
            logger.warning("event_id_card_reconcile_failed", extra={"event_id": event_id})
    return done
