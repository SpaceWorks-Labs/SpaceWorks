"""Personal runtime projection independent of portable tenant datasets."""

from django.apps import apps
from django.db.models import Q
from apps.backup.capture_managers import every_row

RUNTIME_FIELDS = {
    # Personal access is separate from portability: source endpoints and delivery
    # authority never travel in a tenant dump. Only the owning principal can read
    # this explicit projection; credentials, routing snapshots and provider IDs
    # have no personal-export column.
    "integrations.NotificationEnvelope": ("id", "makerspace_id", "feature", "stream", "event", "audience", "scope", "message_body", "source_kind", "source_id", "revision", "timing_policy", "available_at", "processed_at", "created_at"),
    "integrations.NotificationDelivery": ("id", "makerspace_id", "envelope_id", "channel", "provider", "state", "attempt_count", "ambiguous_count", "next_attempt_at", "last_error", "created_at", "updated_at"),
    "integrations.NotificationEndpoint": ("id", "makerspace_id", "channel", "provider", "destination", "provider_subject", "verification_state", "verified_at", "consented_at", "consent_version", "revoked_at", "last_inbound_at", "created_at"),
    "integrations.MessagingDelivery": ("id", "makerspace_id", "channel", "audience", "feature", "event", "context", "status", "progress_rank", "skip_reason", "error_code", "attempts", "estimated_segments", "billed_segments", "created_at", "accepted_at", "sent_at", "delivered_at", "read_at", "failed_at"),
    "accounts.DeviceActivityDay": ("id", "makerspace_id", "platform", "app_version", "local_day", "created_at"),
    "accounts.WebSessionActivityDay": ("id", "makerspace_id", "local_day", "created_at"),
    "notifications.MemberPushDelivery": ("id", "platform", "provider_source", "status", "attempts", "sent_at", "created_at"),
    "integrations.PushDeliveryAttempt": ("id", "platform", "provider_source", "status", "attempts", "sent_at", "created_at"),
}
# Release-2 login security (S-B): the person's own sign-in memory, platform-wide (no space).
from .subject_runtime_security import FIELDS as _SECURITY_FIELDS, security_subject_query  # noqa: E402
RUNTIME_FIELDS.update(_SECURITY_FIELDS)


def runtime_subject_query(model, user, makerspace_id):
    from apps.accounts.staff_identity import actor_ids_for

    label = model._meta.label
    ids = actor_ids_for(user)  # the person and every shell merged into them
    if label in _SECURITY_FIELDS:
        return security_subject_query(model, user)
    if label == "integrations.NotificationEnvelope":
        return every_row(model).filter(recipient__in=ids, makerspace_id=makerspace_id)
    if label == "integrations.NotificationDelivery":
        return every_row(model).filter(envelope__recipient__in=ids, makerspace_id=makerspace_id,
                                    envelope__makerspace_id=makerspace_id)
    if label == "integrations.NotificationEndpoint":
        return every_row(model).filter(user__in=ids, makerspace_id=makerspace_id)
    if label == "integrations.MessagingDelivery":
        return every_row(model).filter(user__in=ids, makerspace_id=makerspace_id)
    if label == "accounts.DeviceActivityDay":
        return every_row(model).filter(grant__user__in=ids).filter(
            Q(makerspace_id=makerspace_id) | Q(makerspace__isnull=True),
        )
    if label == "accounts.WebSessionActivityDay":
        return every_row(model).filter(user__in=ids).filter(
            Q(makerspace_id=makerspace_id) | Q(makerspace__isnull=True),
        )
    if label == "notifications.MemberPushDelivery":
        return every_row(model).filter(envelope_delivery__envelope__recipient__in=ids,
                                    envelope_delivery__makerspace_id=makerspace_id,
                                    envelope_delivery__envelope__makerspace_id=makerspace_id)
    if label == "integrations.PushDeliveryAttempt":
        return every_row(model).filter(recipient__in=ids, delivery_log__makerspace_id=makerspace_id)
    return every_row(model).none()


def runtime_projections(user, makerspace_id):
    for label, fields in RUNTIME_FIELDS.items():
        if apps.is_installed("apps." + label.split(".")[0]):
            model = apps.get_model(label)
            yield label, runtime_subject_query(model, user, makerspace_id).order_by("pk").only(*fields)


def runtime_record(label, row):
    # Model getters apply scoped PII decryption for the proven subject. values()
    # would put ciphertext into their export instead of the readable personal data.
    return {name: getattr(row, name) for name in RUNTIME_FIELDS[label]}
