"""Staff-only configuration, review coverage and application list schemas."""
from rest_framework import serializers
from .api_schema_details import CapacitySerializer, CocSerializer
from .serializers_config import ConfigInput


class ConfigSerializer(ConfigInput):
    operation_id = None
    expected_version = None
    coc_body = None
    id = serializers.IntegerField(allow_null=True)
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())
    coc = CocSerializer(allow_null=True, required=False)
    counts = CapacitySerializer(required=False)


class ReviewApplicationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    alias = serializers.CharField()
    answers = serializers.ListField(child=serializers.DictField())
    blind = serializers.BooleanField()
    blind_notice = serializers.CharField(allow_null=True)
    cohort_id = serializers.IntegerField(allow_null=True, required=False)
    cohort_version = serializers.IntegerField(allow_null=True, required=False)
    review_id = serializers.IntegerField(allow_null=True, required=False)
    draft_batch_id = serializers.IntegerField(allow_null=True, required=False)
    rsvp_due_at = serializers.DateTimeField(allow_null=True, required=False)


class MissingCoverageSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    missing = serializers.IntegerField()


class AssignmentResultSerializer(serializers.Serializer):
    missing_coverage = MissingCoverageSerializer(many=True)
