"""Audited mutation boundary for Events and their registrations."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.audit import services as audit
from apps.events.models import (
    Event,
    EventRegistration,
)
from apps.events.notifications import notify_event_lifecycle
from apps.forms_schema.validation import validate_form_schema

EVENT_FIELDS = frozenset(
    {'title', 'description', 'starts_at', 'ends_at', 'location',
     'location_kind', 'custom_form', 'capacity', 'is_public', 'payment_amount',
     'registration_requires_approval', 'registration_cutoff_at',
     'registration_cutoff_lead_minutes', 'cancellation_cutoff_hours', 'timezone_name',
     'registration_audience', 'category_id', 'tags', 'show_registration_count', 'accent_preset',
     'listing', 'page_state'}
)
INHERITABLE_FIELDS = (EVENT_FIELDS - {"category_id", "tags", "show_registration_count", "accent_preset",
                                      "listing", "page_state"}) | {"image_key"}


def _locked_event(event_id, *, lock_makerspace=True):
    from .services_write_boundary import _held
    if _held.get() is not None and event_id in _held.get()[0]:
        return Event.objects.select_related("makerspace").get(pk=event_id)
    targets = ("self", "makerspace") if lock_makerspace else ("self",)
    return Event.objects.select_for_update(of=targets).select_related("makerspace").get(pk=event_id)


def _validate(instance):
    try:
        instance.full_clean(validate_unique=False, validate_constraints=False)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        raise serializers.ValidationError(detail) from exc
    if isinstance(instance, Event) and instance.ends_at < instance.starts_at:
        detail = {"ends_at": "End time must be at or after start time."}
        raise serializers.ValidationError(detail)


def _canonical_form(value):
    try:
        return validate_form_schema(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'custom_form': exc.messages}) from exc


def _audit(event, actor, action, target, meta=None):
    kwargs = {"makerspace": event.makerspace, "target": target, "meta": meta or {}}
    return audit.record(actor, action, **kwargs)


def _refresh(instance):
    instance.refresh_from_db()
    return instance


def _may_promote(event, now):
    return event.status == Event.Status.PUBLISHED and event.ends_at >= now


