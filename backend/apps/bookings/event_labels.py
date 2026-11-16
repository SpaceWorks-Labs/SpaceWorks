"""Bookings' only seam into event links: labels for bookings that hold a room for an event.

Empty -- every booking reads as an ordinary booking -- when the events app is tombstoned or
the space's `events` module is off, so Bookings keeps working without Events. The events
side decides visibility (`events.booking_calendar_labels`).
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


def event_labels(actor, makerspace, booking_ids):
    from apps.makerspaces.platform import module_enabled
    from apps.separability.tombstones import app_is_tombstoned
    if app_is_tombstoned("events") or not module_enabled(makerspace, "events"):
        return {}
    from apps.events.booking_calendar_labels import linked_event_labels
    return linked_event_labels(actor, makerspace, booking_ids)


class LinkedEventLabelSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=["event", "reserved"],
        help_text="`event` names an event this viewer may see; `reserved` holds the room for an "
                  "event the viewer may not see, so nothing about it is shown.")
    event_id = serializers.IntegerField(required=False)
    title = serializers.CharField(required=False)
    event_status = serializers.ChoiceField(choices=["draft", "published", "cancelled", "completed"], required=False)


LINKED_EVENT_FIELD = extend_schema_field(LinkedEventLabelSerializer(allow_null=True, help_text=(
    "Decision 216: the event this booking (or the booking it replaced) holds the room for. Null when "
    "it holds no event, or Events is off. Only on staff booking lists.")))
