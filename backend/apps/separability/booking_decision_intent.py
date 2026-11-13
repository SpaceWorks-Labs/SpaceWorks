"""Closed typed intent for a single existing-booking decision.

This does not authorize access or resolve portable source IDs. Those operations
must happen before comparing an existing decision or inserting a remapped row.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext

_MAX_ID = 9007199254740991
_FIELDS = frozenset({"version", "makerspace_id", "event_id", "booking_id", "creator_id", "billing_owner"})


def canonical_intent(*, makerspace_id, event_id, booking_id, creator_id):
    values = {"version": 1, "makerspace_id": makerspace_id, "event_id": event_id,
              "booking_id": booking_id, "creator_id": creator_id, "billing_owner": "booking"}
    return validate_intent(values)


def validate_intent(value):
    if not isinstance(value, dict) or set(value) != _FIELDS or type(value["version"]) is not int or value["version"] != 1:
        raise ValidationError(gettext("Invalid booking decision intent."))
    if value["billing_owner"] != "booking":
        raise ValidationError(gettext("Invalid booking decision intent."))
    for name in ("makerspace_id", "event_id", "booking_id", "creator_id"):
        if type(value[name]) is not int or not 1 <= value[name] <= _MAX_ID:
            raise ValidationError(gettext("Invalid booking decision intent."))
    return {name: value[name] for name in sorted(_FIELDS)}
