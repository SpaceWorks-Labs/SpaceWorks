from rest_framework import serializers
from .models import EventRegistration
from .models_broadcasts import EventBroadcast


class EventBroadcastInputSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=10000)
    statuses = serializers.ListField(child=serializers.ChoiceField(choices=EventRegistration.Status.choices),
                                    min_length=1, max_length=6, default=["registered", "attended"])
    attendance = serializers.ChoiceField(choices=["any", "attended", "not_attended"], default="any")


class EventBroadcastSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventBroadcast
        fields = ("id", "event", "subject", "body", "statuses", "attendance", "status", "created_at",
                  "queued_at", "completed_at")
        read_only_fields = fields


class EventBroadcastListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = EventBroadcastSerializer(many=True)


class BulkInviteInputSerializer(serializers.Serializer):
    emails = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=200)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    send_email = serializers.BooleanField(default=True)


class BulkInviteResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
