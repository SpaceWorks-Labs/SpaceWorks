"""Per-device push reporting independent of optional inbox linkage.

P owns the parent FK name. Discover that single concrete relation by model identity
so reporting does not couple its schema to the optional inbox or invent a fallback.
"""
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from apps.integrations.models_tracking import PushDeliveryAttempt


def push_querysets(space_ids):
    """Yield (queryset, tenant path, feature path, audience path) for device ledgers."""
    # Retained T per-device history is not also a canonical push parent outcome.
    yield (PushDeliveryAttempt.objects.filter(delivery_log__makerspace_id__in=space_ids),
           "delivery_log__makerspace_id", "delivery_log__feature", None)
    if not apps.is_installed("apps.notifications"):
        return
    model = apps.get_model("notifications", "MemberPushDelivery")
    parents = [field for field in model._meta.fields if field.is_relation
               and field.related_model._meta.label_lower == "integrations.notificationdelivery"]
    if len(parents) != 1:
        raise ImproperlyConfigured("Push reporting requires P's canonical MemberPushDelivery parent FK.")
    parent = parents[0].name
    # P preserves device-attempt history on the child; parent supplies tenant and
    # feature even if the optional inbox row is removed or was never created.
    qs = model.objects.filter(**{f"{parent}__makerspace_id__in": space_ids})
    yield qs, f"{parent}__makerspace_id", f"{parent}__envelope__feature", f"{parent}__envelope__audience"
