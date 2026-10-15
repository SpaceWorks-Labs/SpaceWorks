"""Explicit projections: no contacts, answers, notes, money or credentials."""

from rest_framework import serializers


class IntegrationBookingResourceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField()
    description = serializers.CharField()
    capacity = serializers.IntegerField()
    location = serializers.CharField()
    is_active = serializers.BooleanField()
    is_public = serializers.BooleanField()


class IntegrationBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    resource_id = serializers.IntegerField(source="space_id")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()
    display_name = serializers.CharField(source="name")
    arrived_at = serializers.DateTimeField(allow_null=True, required=False)

    def __init__(self, *args, attendance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if attendance is False:
            self.fields.pop("arrived_at")


class IntegrationBookingResourcePageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationBookingResourceSerializer(many=True)


class IntegrationBookingPageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationBookingSerializer(many=True)
