from rest_framework import serializers


class RelatedEventSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    registration_status = serializers.CharField()


class RelatedBookingSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    space_name = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    arrived_at = serializers.DateTimeField()
    status = serializers.CharField()


class RelatedMachineSessionSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    source = serializers.CharField()


class PresenceRelatedSerializer(serializers.Serializer):
    event = RelatedEventSerializer(allow_null=True)
    booking = RelatedBookingSerializer(allow_null=True)
    machine_sessions = RelatedMachineSessionSerializer(many=True)
