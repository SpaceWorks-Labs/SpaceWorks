"""Compatibility bridge while Phase-2 lanes migrate domain audience adapters."""
import json
from dataclasses import asdict

from django.utils import timezone

from .models_contract import NotificationEnvelope
from .notification_cutover import guarded, sending_allowed


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
    from .notification_cloud_fanout import free, UnsupportedFanout
    if free():
        pieces, size = [], 0
        for piece in json.JSONEncoder(default=str).iterencode(content):
            size += len(piece.encode())
            if size > 131072:
                raise UnsupportedFanout("Legacy notification snapshot exceeds the free 128 KiB limit.")
            pieces.append(piece)
        envelope.message_body = "".join(pieces)
    else:
        envelope.message_body = json.dumps(content, default=str)
    envelope.save(update_fields=["scope", "message_body"])


@guarded()
def dispatch(envelope, build, sync, occurred_at, event_key):
    from .notify import _run_guarded
    from .notification_cloud_fanout import free, check, preflight
    if free():
        payload = build()
        preflight(envelope.makerspace, payload)
        snapshot(envelope, payload)
        build = lambda: payload
        from django.db import transaction
        from apps.operations.cloud_jobs.contracts import GuardLost
        with transaction.atomic():
            locked = NotificationEnvelope.objects.select_for_update().get(pk=envelope.pk)
            if locked.context.get("free_fanout_state") in {"started", "uncertain"}:
                raise GuardLost("legacy_fanout_requires_reconciliation")
            if locked.processed_at is not None:
                from .notify import NotificationResult
                return NotificationResult(False)
            locked.context = {**locked.context, "free_fanout_state": "started"}
            locked.save(update_fields=["context"])
    def materialize():
        payload = build()
        if not free():
            snapshot(envelope, payload)
        return payload
    if not sending_allowed():
        # Freeze the closure's content durably; no inbox, quota or transport writer
        # runs while the compatibility ingress/conversion barrier is active.
        materialize()
        from .notify import NotificationResult
        return NotificationResult(True)
    result = _run_guarded(envelope.makerspace, envelope.feature, envelope.event,
                          materialize, sync, occurred_at, event_key)
    if free():
        check()
        if result.failed_counts:
            raise GuardLost("legacy_fanout_reported_failure")
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
    from types import SimpleNamespace as InboxDelivery
    content = json.loads(envelope.message_body)
    payload = LifecyclePayload(text=content["text"], emails=tuple(EmailDelivery(**v) for v in content["emails"]),
        scope=NotificationScope.from_dict(envelope.scope), data=content["data"],
        source=content.get("source", {}),
        staff_channels_enabled=content["staff_channels_enabled"], inbox=tuple(InboxDelivery(**v) for v in content["inbox"]))
    return dispatch(envelope, lambda: payload, False, envelope.context["occurred_at"], UUID(envelope.dedup_key.removeprefix("legacy:")))
