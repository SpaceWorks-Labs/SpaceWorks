from rest_framework import serializers


class EventCheckInResolveRequestSerializer(serializers.Serializer):
    checkin_token = serializers.CharField()


class EventCheckInResultSerializer(serializers.Serializer):
    """Attendance operators need identity/state, never roster contacts or answers."""
    id = serializers.IntegerField(read_only=True)
    event_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class EventCheckInResolveResponseSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField(allow_null=True)
    host_waiver_state = serializers.ChoiceField(
        choices=["not_required", "on_file", "missing"]
    )
    event_status = serializers.CharField()
    confirmable = serializers.BooleanField()
