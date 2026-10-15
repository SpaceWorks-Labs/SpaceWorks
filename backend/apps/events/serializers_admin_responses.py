"""Action inputs and paginated event response envelopes."""

from rest_framework import serializers
from .models import Event
from .serializers_event_details import EventAdminSerializer
from .serializers_registration_admin import EventRegistrationAdminSerializer

class EmptyActionSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if data:
            raise serializers.ValidationError(
                {field: 'Unexpected field.' for field in data}
            )
        return value


class EventListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = EventAdminSerializer(many=True)


class EventListWithDefaultsSerializer(EventListResponseSerializer):
    default_registration_audience = serializers.ChoiceField(choices=Event.RegistrationAudience.choices)


class EventRegistrationListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = EventRegistrationAdminSerializer(many=True)
