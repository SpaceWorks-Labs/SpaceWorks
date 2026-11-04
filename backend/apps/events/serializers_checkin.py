from rest_framework import serializers


class EventCheckInResolveRequestSerializer(serializers.Serializer):
    checkin_token = serializers.UUIDField(required=False)
    credential = serializers.CharField(max_length=80, trim_whitespace=False, required=False)

    def validate(self, attrs):
        if set(self.initial_data) - {"checkin_token", "credential"}:
            raise serializers.ValidationError("Unknown check-in field.")
        if ("checkin_token" in attrs) == ("credential" in attrs):
            raise serializers.ValidationError("Provide exactly one checkin_token or credential.")
        return attrs


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
    payment_status = serializers.CharField(allow_null=True, required=False)
    member_id = serializers.IntegerField(allow_null=True, required=False)
    attended_at = serializers.DateTimeField(allow_null=True, required=False)
    ticket_type_name = serializers.CharField(allow_null=True, required=False)
    credential_generation = serializers.IntegerField(required=False)
    host_waiver_state = serializers.ChoiceField(
        choices=["not_required", "on_file", "missing"]
    )
    event_status = serializers.CharField(required=False)
    confirmable = serializers.BooleanField()
