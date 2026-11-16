"""Per-leg idempotency for the legacy lifecycle fan-out: a retried job never resends a leg that already went out."""

def _leg_done(envelope, key):
    """Has this (job, recipient/channel) leg already been handed to its delivery pipeline?"""
    return envelope is not None and key in (envelope.context or {}).get("legs_done", [])


def _mark_leg(envelope, key):
    """Record a finished leg on the shell. Called in the SAME transaction as the leg's log rows, so a retried job
    either sees both or neither and never resends a leg that already went out."""
    if envelope is None:
        return
    from .models_contract import NotificationEnvelope
    locked = NotificationEnvelope.objects.select_for_update().get(pk=envelope.pk)
    legs = sorted({*(locked.context or {}).get("legs_done", []), key})
    locked.context = {**(locked.context or {}), "legs_done": legs}
    locked.save(update_fields=["context"])
    envelope.context = locked.context


def _send_email_leg(makerspace, feature, feature_event, delivery, sync, staff_ids, mandatory):
    from apps.integrations import notify  # resolved late: tests patch notify.dispatch_email
    log = notify.dispatch_email(
        source_kind=delivery.source_kind, source_id=delivery.source_id,
        source_metadata=delivery.source_metadata,
        makerspace=makerspace,
        to_email=delivery.to_email,
        subject=delivery.subject,
        text_body=delivery.text_body,
        html_body=delivery.html_body,
        stream=delivery.stream,
        event=feature_event if mandatory else delivery.mute_event or feature_event,
        audience=delivery.audience,
        persist_body=delivery.persist_body,
        sync=sync,
        recipient_id=delivery.user_id or staff_ids.get(delivery.to_email.strip().casefold()),
        feature=feature,
    )
    return log
