"""Minimal persisted subject used by delivery-time requester selection."""

from apps.integrations.notification_scope_contract import SCOPE_FIELDS, validate_notification_scope


def scope_snapshot(scope):
    data = {} if scope is None else {
        key: getattr(scope, key) for key in SCOPE_FIELDS if getattr(scope, key) is not None
    }
    validate_notification_scope(data)
    return data
