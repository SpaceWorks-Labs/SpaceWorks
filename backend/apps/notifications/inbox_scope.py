"""Minimal persisted subject used by delivery-time requester selection."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError

from apps.integrations.notification_scope_contract import SCOPE_FIELDS, validate_notification_scope


def scope_snapshot(scope):
    data = {} if scope is None else {
        key: getattr(scope, key) for key in SCOPE_FIELDS if getattr(scope, key) is not None
    }
    validate_notification_scope(data)
    return data


def persisted_scope(value):
    """Validate an envelope's stored scope, reading an explicit null as "no subject".

    ``emit`` persists ``NotificationScope.as_dict()``, which spells an absent subject as
    ``None``. Only those nulls are dropped; every other malformed shape, key or
    identifier still raises, so a tampered scope keeps failing closed.
    """
    if not isinstance(value, dict) or value.keys() - SCOPE_FIELDS:
        raise ValidationError(gettext("Invalid notification scope fields."))
    data = {key: item for key, item in value.items() if item is not None}
    validate_notification_scope(data)
    return data
