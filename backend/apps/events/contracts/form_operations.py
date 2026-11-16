"""Stable server-owned inline form identities, independent of answers/order."""

import re
from uuid import UUID, uuid5

_SLOT = re.compile(r"(?:base|stage:[1-9][0-9]*)\Z", re.ASCII)


def child_form_operation_id(outer_id, *, event_id, owner_id, slot):
    if not isinstance(outer_id, UUID):
        raise ValueError("Use a UUID outer operation.")
    if any(type(value) is not int or value <= 0 for value in (event_id, owner_id)):
        raise ValueError("Use positive event and owner IDs.")
    if not isinstance(slot, str) or not _SLOT.fullmatch(slot):
        raise ValueError("Use base or stage:<positive decimal ID>.")
    return uuid5(outer_id, f"events-form:v1:{event_id}:{owner_id}:{slot}")
