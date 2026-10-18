"""Personal runtime projection independent of portable tenant datasets."""

from django.apps import apps
from django.db.models import Q

RUNTIME_FIELDS = {
    # Personal access is separate from portability: source endpoints and delivery
    # authority never travel in a tenant dump. Only the owning principal can read
    # this explicit projection; credentials, routing snapshots and provider IDs
    # have no personal-export column.
    "integrations.NotificationEnvelope": ("id", "makerspace_id", "feature", "stream", "event", "audience", "scope", "message_body", "source_kind", "source_id", "revision", "timing_policy", "available_at", "processed_at", "created_at"),
    "integrations.NotificationDelivery": ("id", "makerspace_id", "envelope_id", "channel", "provider", "state", "attempt_count", "ambiguous_count", "next_attempt_at", "last_error", "created_at", "updated_at"),
    "integrations.NotificationEndpoint": ("id", "makerspace_id", "channel", "provider", "destination", "provider_subject", "verification_state", "verified_at", "consented_at", "consent_version", "revoked_at", "last_inbound_at", "created_at"),
    "integrations.MessagingDelivery": ("id", "makerspace_id", "channel", "audience", "feature", "event", "context", "status", "progress_rank", "skip_reason", "error_code", "attempts", "estimated_segments", "billed_segments", "created_at", "accepted_at", "sent_at", "delivered_at", "read_at", "failed_at"),
    "accounts.DeviceActivityDay": ("id", "makerspace_id", "platform", "local_day", "created_at"),
    "notifications.MemberPushDelivery": ("id", "platform", "provider_source", "status", "attempts", "sent_at", "created_at"),
    "integrations.PushDeliveryAttempt": ("id", "platform", "provider_source", "status", "attempts", "sent_at", "created_at"),
}


def runtime_subject_query(model, user, makerspace_id):
    label = model._meta.label
    if label == "integrations.NotificationEnvelope":
        return model.objects.filter(recipient=user, makerspace_id=makerspace_id)
    if label == "integrations.NotificationDelivery":
        return model.objects.filter(envelope__recipient=user, makerspace_id=makerspace_id,
                                    envelope__makerspace_id=makerspace_id)
    if label == "integrations.NotificationEndpoint":
        return model.objects.filter(user=user, makerspace_id=makerspace_id)
    if label == "integrations.MessagingDelivery":
        return model.objects.filter(user=user, makerspace_id=makerspace_id)
    if label == "accounts.DeviceActivityDay":
        return model.objects.filter(grant__user=user).filter(
            Q(makerspace_id=makerspace_id) | Q(makerspace__isnull=True),
        )
    if label == "notifications.MemberPushDelivery":
        return model.objects.filter(envelope_delivery__envelope__recipient=user,
                                    envelope_delivery__makerspace_id=makerspace_id,
                                    envelope_delivery__envelope__makerspace_id=makerspace_id)
    if label == "integrations.PushDeliveryAttempt":
        return model.objects.filter(recipient=user, delivery_log__makerspace_id=makerspace_id)
    return model.objects.none()


def runtime_projections(user, makerspace_id):
    for label, fields in RUNTIME_FIELDS.items():
        if apps.is_installed("apps." + label.split(".")[0]):
            model = apps.get_model(label)
            yield label, runtime_subject_query(model, user, makerspace_id).order_by("pk").only(*fields)


def runtime_record(label, row):
    # Model getters apply scoped PII decryption for the proven subject. values()
    # would put ciphertext into their export instead of the readable personal data.
    return {name: getattr(row, name) for name in RUNTIME_FIELDS[label]}
