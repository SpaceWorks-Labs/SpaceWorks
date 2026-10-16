"""Minimal persisted subject used by delivery-time requester selection."""

from django.core.exceptions import ValidationError

SCOPE_FIELDS = frozenset({"machine_id", "machine_type_id", "category_id"})


def validate_notification_scope(value):
    if not isinstance(value, dict) or value.keys() - SCOPE_FIELDS:
        raise ValidationError("Invalid notification scope fields.")
    if any(type(item) is not int or not 0 < item <= 9223372036854775807
           for item in value.values()):
        raise ValidationError("Notification scope identifiers must be positive integers.")


def scope_snapshot(scope):
    data = {} if scope is None else {
        key: getattr(scope, key) for key in SCOPE_FIELDS if getattr(scope, key) is not None
    }
    validate_notification_scope(data)
    return data
