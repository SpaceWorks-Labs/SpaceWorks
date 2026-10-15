"""Intentionally minimal projections; contacts, answers and credentials stay private."""

from rest_framework import serializers


class IntegrationEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    status = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    location = serializers.CharField()


class IntegrationParticipantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField(source="name")
    registered_at = serializers.DateTimeField(source="created_at")
    attended_at = serializers.DateTimeField(source="api_attended_at", allow_null=True, required=False)

    def __init__(self, *args, attendance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if attendance is False:
            self.fields.pop("attended_at")


class IntegrationEventPageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationEventSerializer(many=True)


class IntegrationParticipantPageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationParticipantSerializer(many=True)
