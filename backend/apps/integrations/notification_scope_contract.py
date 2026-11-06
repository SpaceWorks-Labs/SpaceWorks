"""Core persisted notification scope contract, also used by the optional inbox."""
from django.utils.translation import gettext
from django.core.exceptions import ValidationError

SCOPE_FIELDS = frozenset({"machine_id", "machine_type_id", "category_id"})


def validate_notification_scope(value):
    if not isinstance(value, dict) or value.keys() - SCOPE_FIELDS:
        raise ValidationError(gettext("Invalid notification scope fields."))
    if any(type(item) is not int or not 0 < item <= 9223372036854775807 for item in value.values()):
        raise ValidationError(gettext("Notification scope identifiers must be positive integers."))
