from rest_framework import serializers

from apps.events.feedback_templates import FEEDBACK_TEMPLATES


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class EventDuplicateSerializer(StrictSerializer):
    attach_series = serializers.BooleanField(default=False, required=False)


class RegistrationAnswersSerializer(StrictSerializer):
    custom_answers = serializers.JSONField(allow_null=True)


class FeedbackTemplateSerializer(StrictSerializer):
    template = serializers.ChoiceField(choices=tuple(FEEDBACK_TEMPLATES))


class TicketPublicFieldsSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    location = serializers.CharField(read_only=True)
    public_token = serializers.UUIDField(read_only=True)
    timezone_name = serializers.CharField(read_only=True)


class MemberEventTicketSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    event = TicketPublicFieldsSerializer(read_only=True)
    ticket_png_available = serializers.BooleanField(read_only=True)
