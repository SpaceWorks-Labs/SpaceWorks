"""Persist in the caller's transaction; broker failure leaves a recoverable intent."""
import json
import logging

from django.db import transaction
from django.utils import timezone

from apps.notifications.preferences import mandatory_email
from .dispatch_policy import never_deferred
from .models_contract import NotificationEnvelope

logger = logging.getLogger(__name__)


def enqueue(envelope_id):
    from .mail_providers.outbox import enqueue_inline_allowed
    if not enqueue_inline_allowed():
        return
    from .notification_tasks import deliver_envelope
    try:
        deliver_envelope.delay(envelope_id)
    except Exception:
        logger.warning("notification_outbox_enqueue_failed", extra={"envelope_id": envelope_id})


def emit(*, makerspace, recipient, feature, stream, event, audience, dedup_key,
         source_kind, source_id, revision="1", subject=None, scope=None, context=None,
         rendered=None, timing_policy="immediate", available_at=None):
    """Phase-2 adapter seam. Source registry is required, including account-only owners."""
    if audience not in {"staff", "requester", "member"} or recipient is None:
        raise ValueError("A personal envelope requires an explicit recipient and audience")
    if timing_policy not in {"immediate", "deferred", "digest"}:
        raise ValueError("Invalid notification timing policy")
    if not dedup_key or len(dedup_key) > 200:
        raise ValueError("Invalid notification dedup key")
    for value, maximum in ((feature, 32), (stream, 32), (event, 64), (source_kind, 64), (str(source_id), 64), (str(revision), 64)):
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError("Invalid notification identity field")
    if not source_kind or not event:
        raise ValueError("Source and event are required")
    scope = scope.as_dict() if hasattr(scope, "as_dict") else scope or {}
    if not isinstance(scope, dict) or set(scope) - {"machine_id", "machine_type_id", "category_id"}:
        raise ValueError("Invalid notification scope")
    if any(value is not None and (type(value) is not int or value < 1) for value in scope.values()):
        raise ValueError("Invalid notification scope identifier")
    # Context is for safe template variables. Bearers and private content belong
    # neither in this JSON nor in append-only audit metadata.
    if callable(rendered):
        # Built in the RECIPIENT's language, not the sender's request language.
        from config.locale_resolution import override_for
        with override_for(user=recipient, makerspace=makerspace):
            rendered = {key: (str(value) if value is not None else value) for key, value in rendered().items()}
    context = context or {}
    if not isinstance(context, dict) or not isinstance(rendered or {}, dict):
        raise ValueError("Notification content must be an object")
    denied = {"password", "token", "secret", "email", "phone", "contact", "credentials", "destination"}
    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str) or any(part in key.casefold() for part in denied):
                    raise ValueError("Sensitive notification context key")
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(context)
    encoded = json.dumps(context)
    body = json.dumps(rendered or {})
    if len(encoded) > 16000 or len(body) > 100000:
        raise ValueError("Notification content is too large")
    if never_deferred(stream, event):
        timing_policy, available_at = "immediate", None
    elif timing_policy == "digest":
        from apps.makerspaces.platform import feature_enabled
        if not feature_enabled(makerspace, "notifications.digests"):
            raise ValueError("Email digests are disabled")
        from datetime import time
        from types import SimpleNamespace
        from .notification_resolution import selected_policy
        from .quiet_hours import next_wall_time, timing_policy as tenant_timing
        channels, _ = selected_policy(SimpleNamespace(makerspace=makerspace, recipient=recipient,
            recipient_id=recipient.pk, makerspace_id=makerspace.pk, feature=feature))
        if any(channel != "email" for channel in channels):
            raise ValueError("Digests support email only")
        policy = tenant_timing(makerspace)
        available_at = next_wall_time(makerspace, timezone.now(), policy.digest_at if policy else time(8))
    subject_type = None
    if subject is not None:
        from django.contrib.contenttypes.models import ContentType
        subject_type = ContentType.objects.get_for_model(subject)
    from .models_endpoints import NotificationEndpoint
    bindings = {endpoint.channel: {"id": endpoint.pk, "generation": endpoint.integration_generation,
                                  "provider": endpoint.provider, "identity": endpoint.integration_identity}
                for endpoint in NotificationEndpoint.objects.filter(makerspace=makerspace, user=recipient, revoked_at=None)}
    from types import SimpleNamespace
    from .notification_addressed import snapshot as sms_snapshot
    sms_binding = sms_snapshot(SimpleNamespace(makerspace=makerspace, recipient=recipient))
    if sms_binding:
        bindings["sms"] = sms_binding
    with transaction.atomic():
        envelope, created = NotificationEnvelope.objects.get_or_create(dedup_key=dedup_key, defaults={
            "makerspace": makerspace, "recipient": recipient, "feature": feature,
            "stream": stream, "event": event, "audience": audience,
            "source_kind": source_kind, "source_id": str(source_id), "revision": str(revision),
            "subject_type": subject_type, "subject_id": str(subject.pk) if subject else "",
            "scope": scope.as_dict() if hasattr(scope, "as_dict") else scope or {},
            "context": context, "message_body": body, "timing_policy": timing_policy,
            "routing_snapshot": bindings,
            "available_at": available_at, "mandatory": mandatory_email(stream, event),
        })
        if (envelope.makerspace_id, envelope.recipient_id, envelope.event) != (makerspace.pk, recipient.pk, event):
            raise ValueError("Notification dedup key belongs to another intent")
        if created:
            transaction.on_commit(lambda: enqueue(envelope.pk), robust=True)
    return envelope


def ready(envelope, now=None):
    now = now or timezone.now()
    if never_deferred(envelope.stream, envelope.event):
        return True
    if envelope.available_at and envelope.available_at > now:
        return False
    from .quiet_hours import quiet_until
    from .notification_resolution import resolve
    channels = [target.channel for target in resolve(envelope)]
    untils = [quiet_until(envelope.makerspace, channel, now) for channel in channels]
    untils = [value for value in untils if value]
    if untils:
        NotificationEnvelope.objects.filter(pk=envelope.pk).update(available_at=max(untils))
        return False
    return True
