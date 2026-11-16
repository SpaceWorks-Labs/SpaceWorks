"""Concrete command, page and virtual context shapes for OpenAPI consumers."""
from rest_framework import serializers
from .serializers import StageAssignmentSerializer, StageDefinitionSerializer


class FormIntentStatusSerializer(serializers.Serializer):
    slot = serializers.CharField()
    operation_id = serializers.UUIDField()
    intent_id = serializers.UUIDField(allow_null=True)
    state = serializers.ChoiceField(choices=("pending", "not_requested"))
    fields = serializers.DictField()
    status_url = serializers.CharField(allow_null=True)


class StageMutationResult(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    response_id = serializers.IntegerField(allow_null=True, required=False)
    response_version = serializers.IntegerField(allow_null=True, required=False)
    assignment_id = serializers.IntegerField(required=False)
    assignment_version = serializers.IntegerField(required=False)
    pinned_form_revision_id = serializers.IntegerField(required=False)
    due_at = serializers.DateTimeField(required=False)
    allowed_actions = serializers.ListField(child=serializers.CharField(), required=False)
    save_intent = serializers.UUIDField(allow_null=True, required=False)
    save_operation_id = serializers.UUIDField(allow_null=True, required=False)
    form_save_intents = FormIntentStatusSerializer(many=True, required=False)


class StageDefinitionResult(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    form_id = serializers.UUIDField(required=False)
    revision_id = serializers.IntegerField(allow_null=True, required=False)


class StageActivationPreview(serializers.Serializer):
    preview = serializers.BooleanField()
    eligible_participant_ids = serializers.ListField(child=serializers.IntegerField())


class StageActivationResult(StageDefinitionResult):
    stage_form_id = serializers.IntegerField()


class StageShortlistResult(StageDefinitionResult):
    milestone_ids = serializers.ListField(child=serializers.IntegerField())


class StageVirtualContext(serializers.Serializer):
    stage_form_id = serializers.IntegerField()
    schema = serializers.DictField()
    event_date_revision = serializers.IntegerField()
    response_id = serializers.IntegerField(allow_null=True)


class AssignmentPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = StageAssignmentSerializer(many=True)


class DefinitionPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = StageDefinitionSerializer(many=True)
