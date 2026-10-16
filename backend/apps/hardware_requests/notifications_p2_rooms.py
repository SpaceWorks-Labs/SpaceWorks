"""Equipment staff room intents, persisted before the domain transaction commits."""
from types import SimpleNamespace

from django.db import transaction

from apps.accounts import rbac
from apps.integrations.destinations import NotificationScope, resolve_destinations
from apps.integrations.dispatch_channels import dispatch_channel
from apps.integrations.models import NotificationDeliveryLog
from apps.integrations.notification_catalog import is_notification_enabled
from apps.integrations.notification_sources import source_eligible
from apps.integrations.recipients import feature_available
from apps.makerspaces.servability import is_servable

ROOM_CHANNELS = ("telegram", "slack", "mattermost", "discord", "webhook")


@transaction.atomic
def queue_rooms(*, space, feature, event, kind, source, version, subject, scope, context, body, key):
    # Serialise repeated fan-out on the domain row, without inventing another model.
    type(subject).objects.select_for_update().get(pk=subject.pk)
    payload = {"equipment_source": kind, "source_id": str(source),
               "revision": version, "context": context, "intent_key": key,
               "scope": scope.as_dict()}
    for channel in ROOM_CHANNELS:
        if not is_notification_enabled(space, feature, channel):
            continue
        if rbac.scope_notification_policy(NotificationDeliveryLog.objects.all(),
                makerspace_id=space.pk).filter(channel=channel, payload__intent_key=key).exists():
            continue
        dispatch_channel(makerspace=space, feature=feature, event=event, channel=channel,
                         text_body=body, payload=payload, scope=scope)


def eligible_room(log):
    """Hook for the existing room transport, before every send/retry/release."""
    payload = log.payload or {}
    kind = payload.get("equipment_source")
    if not kind:
        return True
    space = log.makerspace
    space.refresh_from_db()
    if not is_servable(space):
        return False
    # The machine source owns printer vs generic module eligibility. The shared
    # personal resolver still needs the corresponding source-aware gate (report).
    if kind != "machines.service" and not feature_available(space, log.feature):
        return False
    if not is_notification_enabled(space, log.feature, log.channel):
        return False
    scope = NotificationScope.from_dict(payload.get("scope"))
    if not any(getattr(row, "pk", None) == log.destination_id
               for row in resolve_destinations(space, log.channel, scope)):
        return False
    envelope = SimpleNamespace(source_kind=kind, source_id=payload.get("source_id"),
        revision=payload.get("revision"), context=payload.get("context", {}),
        makerspace=space, makerspace_id=space.pk, recipient_id=None,
        audience="staff", event=log.event, feature=log.feature,
        scope=payload.get("scope", {}))
    return source_eligible(envelope)
