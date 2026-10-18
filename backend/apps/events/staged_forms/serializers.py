"""Closed staged command envelopes and explicit revision-detail response types."""
from rest_framework import serializers
from apps.events.programme.serializers import ClosedSerializer, ErrorSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 423, 429, 503)}


class StageCommand(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class StageConfigurationCommand(StageCommand):
    settings = serializers.DictField()
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
    response_id = serializers.IntegerField()
    response_version = serializers.IntegerField()
    required = serializers.BooleanField()
    blocked_actions = serializers.ListField(child=serializers.CharField())


class StageResponseDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    assignment = StageAssignmentSerializer()
    selected_revision = serializers.IntegerField(allow_null=True)
    schema = serializers.DictField()
    answers = serializers.DictField()
    event_date_revision = serializers.IntegerField()


class StageResponseFinanceDetailSerializer(StageResponseDetailSerializer):
    """Distinct operation documents the finance-only sensitive projection."""


class StageDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        from .definition_models import EventStageForm
        model = EventStageForm
        fields = ("id", "slug", "title", "stage", "state", "version", "form_id", "current_revision_id",
                  "required", "missed_action", "blocked_actions", "audience", "opens_at", "due_at")
