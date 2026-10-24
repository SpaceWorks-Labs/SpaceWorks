"""Closed operation payloads and explicit OpenAPI response shapes."""

from rest_framework import serializers
from apps.forms_schema.serializers import FormEditorDocumentField


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unknown field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.DictField(required=False)
    current_version = serializers.IntegerField(required=False)


ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}


class CommandSerializer(ClosedSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    operation_id = serializers.UUIDField()


class PublishingInput(CommandSerializer):
    is_public = serializers.BooleanField(required=False)
    registration_audience = serializers.ChoiceField(
        choices=("members", "accounts", "invite", "participating_organizations"), required=False)
    status = serializers.ChoiceField(choices=("draft", "published"), required=False)
    release_saved_website = serializers.BooleanField(default=False)
    website_revision = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if attrs["release_saved_website"] and "website_revision" not in attrs:
            raise serializers.ValidationError({"website_revision": "Choose the saved website revision."})
        return attrs


class AggregateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class PublishingSerializer(AggregateSerializer):
    is_public = serializers.BooleanField()
    registration_audience = serializers.CharField()
    status = serializers.CharField()
    website_released = serializers.BooleanField()
    website_revision = serializers.IntegerField(allow_null=True)


class ReadinessItemSerializer(serializers.Serializer):
    code = serializers.CharField()
    status = serializers.ChoiceField(choices=("ready", "missing", "action", "unavailable"))
    label = serializers.CharField()
    href = serializers.CharField()
    count = serializers.IntegerField(min_value=0, allow_null=True)


class ReadinessSerializer(AggregateSerializer):
    generated_at = serializers.DateTimeField()
    items = ReadinessItemSerializer(many=True)


class ArrivalSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    count = serializers.IntegerField(min_value=0)


class LiveSerializer(AggregateSerializer):
    generated_at = serializers.DateTimeField()
    available_from = serializers.DateTimeField()
    doors_open_at = serializers.DateTimeField()
    seconds_until_doors = serializers.IntegerField(min_value=0)
    active = serializers.BooleanField()
    going = serializers.IntegerField(min_value=0)
    checked_in = serializers.IntegerField(min_value=0)
    arrivals = ArrivalSerializer(many=True)
    first_run = serializers.BooleanField()


class FormSelector(ClosedSerializer):
    posting_id = serializers.IntegerField(min_value=1, required=False)
    round_id = serializers.IntegerField(min_value=1, required=False)
    track_id = serializers.IntegerField(min_value=1, required=False)


class FormPutInput(CommandSerializer, FormSelector):
    schema = FormEditorDocumentField(allow_null=True)


class FormValidationInput(FormSelector):
    schema = FormEditorDocumentField(allow_null=True)
    sample_answers = serializers.DictField(required=False, default=dict)


class FormSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    form_key = serializers.CharField()
    schema = FormEditorDocumentField(allow_null=True)


class FormValidationSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    visible_question_ids = serializers.ListField(child=serializers.CharField())
    errors = serializers.DictField()
