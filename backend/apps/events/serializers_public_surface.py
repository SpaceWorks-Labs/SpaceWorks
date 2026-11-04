"""Staff read fields for the public surface: who can find, page state and online delivery.

The join link is plaintext only for staff who hold EDIT_DETAILS on the event; anyone else
in the staff console (check-in staff, judges) sees just whether one is set.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .event_permissions import EDIT_DETAILS
from .models import Event

PUBLIC_SURFACE_FIELDS = ("listing", "page_state", "delivery_mode", "join_url", "join_url_set")


class EventPublicSurfaceFields(serializers.Serializer):
    listing = serializers.ChoiceField(choices=Event.Listing.choices, read_only=True)
    page_state = serializers.ChoiceField(choices=Event.PageState.choices, read_only=True)
    delivery_mode = serializers.ChoiceField(choices=Event.DeliveryMode.choices, read_only=True)
    join_url = serializers.SerializerMethodField(
        help_text="Online join link; null unless the reader holds edit_details on this event.")
    join_url_set = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_join_url(self, obj):
        from .online_delivery import enabled, stored_join_url
        if not obj.join_url_encrypted or EDIT_DETAILS not in self._authority(obj)[1] or not enabled(obj):
            return None
        return stored_join_url(obj) or None

    @extend_schema_field(serializers.BooleanField())
    def get_join_url_set(self, obj):
        return bool(obj.join_url_encrypted)


class EventPublicSurfaceInput(serializers.Serializer):
    """Write fields mixed into the event create/update serializer."""

    listing = serializers.ChoiceField(choices=Event.Listing.choices, required=False)
    page_state = serializers.ChoiceField(choices=Event.PageState.choices, required=False)
    delivery_mode = serializers.ChoiceField(choices=Event.DeliveryMode.choices, required=False)
    join_url = serializers.CharField(max_length=2000, allow_blank=True, required=False, write_only=True,
                                     help_text="https:// link released only to confirmed registrants.")

    def validate_join_url(self, value):
        from .online_delivery import validate_join_url
        return validate_join_url(value)
