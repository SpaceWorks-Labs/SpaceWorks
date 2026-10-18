"""Closed staged command envelopes and explicit revision-detail response types."""
from rest_framework import serializers
from apps.events.programme.serializers import ClosedSerializer, ErrorSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 423, 429, 503)}


class StageCommand(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            for key, field in self.fields.items():
                if key in data and data[key] is not None and (
                    isinstance(field, serializers.IntegerField) and type(data[key]) is not int or
                    isinstance(field, serializers.BooleanField) and type(data[key]) is not bool):
                    raise serializers.ValidationError({"code": "invalid_stage_command", "fields": {key: ["Use the declared JSON type."]}})
        return super().to_internal_value(data)


class StageSettingsSerializer(ClosedSerializer):
    slug = serializers.SlugField(max_length=64, required=False)
    title = serializers.CharField(max_length=200, required=False)
    stage = serializers.ChoiceField(choices=("application", "shortlisted", "accepted_rsvp", "pre_event", "post_event"), required=False)
    activation_point = serializers.ChoiceField(choices=("", "accepted", "rsvp"), required=False)
    opening_mode = serializers.ChoiceField(choices=("trigger", "absolute", "event_start", "event_end"), required=False)
    opens_at = serializers.DateTimeField(allow_null=True, required=False)
    opening_offset_seconds = serializers.IntegerField(min_value=-31536000, max_value=31536000, allow_null=True, required=False)
    due_mode = serializers.ChoiceField(choices=("absolute", "after_trigger", "event_start", "event_end"), required=False)
    due_at = serializers.DateTimeField(allow_null=True, required=False)
    due_after_seconds = serializers.IntegerField(min_value=1, max_value=31536000, allow_null=True, required=False)
    due_event_offset_seconds = serializers.IntegerField(min_value=-31536000, max_value=31536000, allow_null=True, required=False)
    reminder_offsets = serializers.ListField(child=serializers.IntegerField(min_value=-31536000, max_value=-1), max_length=10, required=False)
    required = serializers.BooleanField(required=False)
    missed_action = serializers.ChoiceField(choices=("none", "warn", "block"), required=False)
    blocked_actions = serializers.ListField(child=serializers.ChoiceField(choices=("rsvp", "check_in", "claim_submit")), max_length=3, required=False)
    lock_on_next_stage = serializers.BooleanField(required=False)
    audience = serializers.DictField(required=False)


class StageConfigurationCommand(StageCommand):
    settings = StageSettingsSerializer()
    schema = serializers.DictField(required=False)


class StageResponseCommand(StageCommand):
    expected_assignment_version = serializers.IntegerField(min_value=1)
    form = serializers.DictField()
    answers = serializers.DictField()
    derivations = serializers.DictField(default=dict)
    save_choices = serializers.DictField(child=serializers.BooleanField(), default=dict)
    saved_detail_versions = serializers.DictField(child=serializers.IntegerField(min_value=0), default=dict)
    event_date_revision = serializers.IntegerField(min_value=1)


class StageDraftCommand(StageCommand):
    creation_operation_id = serializers.UUIDField(required=False)


class StageActivationCommand(StageCommand):
    preview = serializers.BooleanField(default=True)
    confirmed = serializers.BooleanField(default=False)
    due_at = serializers.DateTimeField()
    participant_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=1000, allow_empty=False)


class CancelStageAssignmentCommand(StageCommand):
    expected_response_version = serializers.IntegerField(min_value=1, allow_null=True)
    expected_stage_form_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")
    reason = serializers.CharField(max_length=5000)
    confirmed = serializers.BooleanField()


class ReassignStageAssignmentCommand(CancelStageAssignmentCommand):
    replacement_form_revision_id = serializers.IntegerField(min_value=1)
    due_at = serializers.DateTimeField()


class ExtendStageAssignmentCommand(CancelStageAssignmentCommand):
    due_at = serializers.DateTimeField()


class ShortlistCommand(StageCommand):
    participant_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, allow_empty=False)
    published = serializers.BooleanField()
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")


class StageAssignmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    stage_form_id = serializers.IntegerField()
    title = serializers.CharField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    due_at = serializers.DateTimeField()
    opens_at = serializers.DateTimeField()
    due_revision = serializers.IntegerField()
    pinned_form_revision_id = serializers.IntegerField()
    response_id = serializers.IntegerField(allow_null=True)
    response_version = serializers.IntegerField(allow_null=True)
    required = serializers.BooleanField()
    blocked_actions = serializers.ListField(child=serializers.CharField())
    schema = serializers.DictField()
    response_revision = serializers.IntegerField(allow_null=True, required=False)
    detail_url = serializers.CharField(allow_null=True, required=False)
    finance_detail_url = serializers.CharField(allow_null=True, required=False)
    allowed_actions = serializers.ListField(child=serializers.CharField(), required=False)


class StageAnswerReviewSerializer(serializers.Serializer):
    date_revision = serializers.IntegerField()
    locked = serializers.BooleanField()


class StageOwnerResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    assignment = StageAssignmentSerializer()
    selected_revision = serializers.IntegerField(allow_null=True)
    schema = serializers.DictField()
    answers = serializers.DictField()
    event_date_revision = serializers.IntegerField()
    answer_review = StageAnswerReviewSerializer()
    omitted_question_ids = serializers.ListField(child=serializers.CharField())
    allowed_actions = serializers.ListField(child=serializers.CharField())


class StageResponseDetailSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    stage_form_id = serializers.IntegerField()
    assignment_id = serializers.IntegerField()
    response_id = serializers.IntegerField()
    response_version = serializers.IntegerField()
    response_revision = serializers.IntegerField()
    form = serializers.DictField()
    submitted_at = serializers.DateTimeField()
    projection = serializers.ChoiceField(choices=("organizer", "finance"))
    answers = serializers.DictField()
    answer_review = StageAnswerReviewSerializer()
    omitted_question_ids = serializers.ListField(child=serializers.CharField())


class StageResponseFinanceDetailSerializer(StageResponseDetailSerializer):
    """Distinct operation documents the finance-only sensitive projection."""


class StageDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        from .definition_models import EventStageForm
        model = EventStageForm
        fields = ("id", "slug", "title", "stage", "state", "version", "form_id", "current_revision_id",
                  "required", "missed_action", "blocked_actions", "audience", "opens_at", "due_at", "activation_point",
                  "opening_mode", "opening_offset_seconds", "due_mode", "due_after_seconds", "due_event_offset_seconds",
                  "reminder_offsets", "lock_on_next_stage")


class StageDefinitionDetailSerializer(StageDefinitionSerializer):
    schema = serializers.SerializerMethodField()

    def get_schema(self, obj):
        return obj.current_revision.schema if obj.current_revision_id else None

    class Meta(StageDefinitionSerializer.Meta):
        fields = (*StageDefinitionSerializer.Meta.fields, "schema")
