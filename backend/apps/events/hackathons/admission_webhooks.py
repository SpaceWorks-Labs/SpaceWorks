"""Application status on the staff rooms and webhooks (lane L21a).

The `events` family carries the event, application, registration and stage IDs; the
status is the event name itself (`events.application_offered`, ...). Answers, scores,
reviewer identities and names never ride this payload: rooms receive one neutral line.
"""
import logging

from django.db import transaction

from apps.integrations.fanout_jobs import deferred_fanout
from apps.integrations.notification_catalog import FEATURE_EVENTS

logger = logging.getLogger(__name__)


@deferred_fanout(feature="events")
def application_changed(event, application, name, *, stage=None):
    if name not in FEATURE_EVENTS.get("events", ()):
        return None
    from apps.integrations.notify import LifecyclePayload, notify_lifecycle
    from .admission_stages import current_stage
    try:
        stage = stage or current_stage(application)
    except Exception:
        stage = None
    status = name.removeprefix("application_").replace("_", " ")
    data = {"event_id": event.pk, "application_id": application.pk,
            "registration_id": application.registration_id, "stage_id": stage.pk if stage else None,
            "stage_position": stage.position if stage else None}
    text = f"Application #{application.pk} for {event.title}: {status}."

    def build():
        return LifecyclePayload(text=text, data=data, source={"source_kind": "events.application_status",
                                                              "source_id": str(application.pk)})
    try:
        with transaction.atomic():  # a notification failure never poisons the admission transaction
            return notify_lifecycle(event.makerspace, feature="events", event=name, build=build)
    except Exception:
        logger.warning("application_webhook_failed", extra={"application_id": application.pk})
        return None
