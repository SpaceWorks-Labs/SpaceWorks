"""Personal runtime projection independent of portable tenant datasets."""

from django.apps import apps
from django.db.models import Q

RUNTIME_FIELDS = {
    "accounts.DeviceActivityDay": ("id", "makerspace_id", "platform", "local_day", "created_at"),
    "notifications.MemberPushDelivery": ("id", "platform", "provider_source", "status", "attempts", "sent_at", "created_at"),
    "integrations.PushDeliveryAttempt": ("id", "platform", "provider_source", "status", "attempts", "sent_at", "created_at"),
}


def runtime_subject_query(model, user, makerspace_id):
    label = model._meta.label
    if label == "accounts.DeviceActivityDay":
        return model.objects.filter(grant__user=user).filter(
            Q(makerspace_id=makerspace_id) | Q(makerspace__isnull=True),
        )
    if label == "notifications.MemberPushDelivery":
        return model.objects.filter(inbox_row__user=user,
                                    inbox_row__makerspace_id=makerspace_id)
    if label == "integrations.PushDeliveryAttempt":
        return model.objects.filter(recipient=user, delivery_log__makerspace_id=makerspace_id)
    return model.objects.none()


def runtime_projections(user, makerspace_id):
    for label, fields in RUNTIME_FIELDS.items():
        if apps.is_installed("apps." + label.split(".")[0]):
            model = apps.get_model(label)
            yield label, runtime_subject_query(model, user, makerspace_id).order_by("pk").values(*fields)
