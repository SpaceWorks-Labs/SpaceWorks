"""Compatibility bridge while Phase-2 lanes migrate domain audience adapters."""
import json
from dataclasses import asdict

from django.utils import timezone

from .models_contract import NotificationEnvelope


def persist(makerspace, feature, event, payload, event_key, occurred_at):
    return NotificationEnvelope.objects.create(makerspace=makerspace, feature=feature,
        stream="hardware" if feature == "hardware_requests" else feature, event=event,
        audience="staff", source_kind="legacy.lifecycle", dedup_key=f"legacy:{event_key}",
        context={"occurred_at": occurred_at}, revision="1")


def snapshot(envelope, payload):
    # Rendered legacy bodies are PII, so they use the scoped encrypted field. Redacted
    # security mail cannot be persisted or reconstructed; those callers remain sync.
    emails = [asdict(email) for email in payload.emails if email.persist_body]
    content = {"text": payload.text, "emails": emails, "data": payload.data,
               "source": payload.source,
               "staff_channels_enabled": payload.staff_channels_enabled,
               "inbox": [asdict(item) for item in payload.inbox]}
    envelope.scope = payload.scope.as_dict() if payload.scope else {}
    envelope.message_body = json.dumps(content, default=str)
    envelope.save(update_fields=["scope", "message_body"])


def dispatch(envelope, build, sync, occurred_at, event_key):
    from .notify import _run_guarded
    def materialize():
        payload = build()
        snapshot(envelope, payload)
        return payload
    result = _run_guarded(envelope.makerspace, envelope.feature, envelope.event,
                          materialize, sync, occurred_at, event_key)
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(processed_at=timezone.now())
    return result


def recover(envelope):
    if not envelope.message_body:
        # Legacy closures cannot be serialized. Phase-2 adapters replace these shells
        # with source-backed emit() calls, whose content is durable before commit.
        return
    from uuid import UUID
    from .destinations import NotificationScope
    from .notify import EmailDelivery, LifecyclePayload
    from apps.notifications.inbox import InboxDelivery
    content = json.loads(envelope.message_body)
    payload = LifecyclePayload(text=content["text"], emails=tuple(EmailDelivery(**v) for v in content["emails"]),
        scope=NotificationScope.from_dict(envelope.scope), data=content["data"],
        source=content.get("source", {}),
        staff_channels_enabled=content["staff_channels_enabled"], inbox=tuple(InboxDelivery(**v) for v in content["inbox"]))
    return dispatch(envelope, lambda: payload, False, envelope.context["occurred_at"], UUID(envelope.dedup_key.removeprefix("legacy:")))
