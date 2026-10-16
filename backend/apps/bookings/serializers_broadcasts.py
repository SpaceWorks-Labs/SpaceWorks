from django.utils import timezone
from rest_framework import serializers
from rest_framework.settings import api_settings

from .models_broadcasts import BookingBroadcast


class BookingBroadcastInputSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000)
    window_start = serializers.DateTimeField(default=timezone.now)
    window_end = serializers.DateTimeField()
    statuses = serializers.ListField(child=serializers.ChoiceField(choices=["pending", "confirmed"]),
                                    min_length=1, max_length=2, default=["confirmed"])

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, dict) else set()
        if unknown:
            # Field-keyed: a bare list from a top-level to_internal_value breaks .errors.
            raise serializers.ValidationError({key: ["Unexpected field."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class BookingBroadcastSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(max_length=200, read_only=True)
    body = serializers.CharField(max_length=10000, read_only=True)
    statuses = serializers.ListField(child=serializers.ChoiceField(choices=["pending", "confirmed"]),
                                    min_length=1, max_length=2, read_only=True)

    class Meta:
        model = BookingBroadcast
        fields = ("id", "space", "subject", "body", "window_start", "window_end", "statuses", "status",
                  "created_at", "queued_at", "completed_at")
        read_only_fields = fields


class BookingBroadcastListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = BookingBroadcastSerializer(many=True)


class BookingBroadcastActionSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if data:
            raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY: ["This action accepts no fields."]})
        return super().to_internal_value(data)
