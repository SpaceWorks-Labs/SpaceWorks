"""Closed payloads and response shapes for review stages and the panel workspace (lane L21a)."""
from rest_framework import serializers

from .admission_inputs import CommandInput, LiteralBoolean, StrictSerializer


class CriterionSerializer(StrictSerializer):
    key = serializers.RegexField(r"^[a-z][a-z0-9_]{0,39}$")
    label = serializers.CharField(max_length=120)
    guidance = serializers.CharField(max_length=500, required=False, allow_blank=True)


class StageFields(CommandInput):
    name = serializers.CharField(max_length=120, required=False)
    reviews_per_application = serializers.IntegerField(min_value=1, max_value=20, required=False)
    blind = LiteralBoolean(required=False)
    criteria = CriterionSerializer(many=True, required=False, max_length=10)
    guidance = serializers.CharField(max_length=4000, allow_blank=True, required=False)
    opens_at = serializers.DateTimeField(allow_null=True, required=False)
    closes_at = serializers.DateTimeField(allow_null=True, required=False)
    assignment_strategy = serializers.ChoiceField(choices=["balanced", "random"], required=False)


class StageCreateInput(StageFields):
    name = serializers.CharField(max_length=120)


class StageUpdateInput(StageFields):
    state = serializers.ChoiceField(choices=["draft", "open", "closed"], required=False)


class PanelInput(CommandInput):
    reviewer_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=200)


class PreviewInput(StrictSerializer):
    seed = serializers.RegexField(r"^[A-Za-z0-9_-]{1,64}$", required=False)
    strategy = serializers.ChoiceField(choices=["balanced", "random"], required=False)


class ApplyInput(CommandInput):
    seed = serializers.RegexField(r"^[A-Za-z0-9_-]{1,64}$")
    strategy = serializers.ChoiceField(choices=["balanced", "random"])
    fingerprint = serializers.RegexField(r"^[0-9a-f]{64}$")


class StageReviewInput(StrictSerializer):
    scores = serializers.DictField(child=serializers.IntegerField(min_value=1, max_value=5), required=False)
    notes = serializers.CharField(max_length=5000, allow_blank=True, required=False, default="")
    recusal_code = serializers.ChoiceField(choices=["self", "team", "affiliation", "declared"], required=False)

    def validate(self, attrs):
        if ("scores" in attrs) == ("recusal_code" in attrs):
            raise serializers.ValidationError("Submit scores or recuse.")
        return attrs


class StageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    position = serializers.IntegerField()
    name = serializers.CharField()
    state = serializers.CharField()
    version = serializers.IntegerField()
    reviews_per_application = serializers.IntegerField()
    blind = serializers.BooleanField()
    criteria = CriterionSerializer(many=True)
    guidance = serializers.CharField()
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    assignment_strategy = serializers.CharField()
    assignment_seed = serializers.CharField()
    assigned_at = serializers.DateTimeField(allow_null=True)
    frozen = serializers.BooleanField()
    panel = serializers.ListField(child=serializers.DictField())
    standing = serializers.IntegerField()


class PlanPairSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    reviewer_id = serializers.IntegerField()


class PlanSerializer(serializers.Serializer):
    stage_id = serializers.IntegerField()
    strategy = serializers.CharField()
    seed = serializers.CharField()
    fingerprint = serializers.CharField()
    pairs = PlanPairSerializer(many=True)
    deficits = serializers.ListField(child=serializers.DictField())
    loads = serializers.ListField(child=serializers.DictField())
    applications = serializers.IntegerField()


class ApplyResultSerializer(serializers.Serializer):
    stage = StageSerializer()
    created = serializers.IntegerField()


class ProgressRowSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    alias = serializers.CharField()
    state = serializers.CharField()
    version = serializers.IntegerField()
    reviews = serializers.IntegerField()
    needed = serializers.IntegerField()
    average = serializers.FloatField(allow_null=True)


class ReviewerStageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    event_title = serializers.CharField(required=False)
    position = serializers.IntegerField()
    name = serializers.CharField()
    state = serializers.CharField()
    blind = serializers.BooleanField()
    criteria = CriterionSerializer(many=True)
    guidance = serializers.CharField()
    reviews_per_application = serializers.IntegerField()
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    assigned = serializers.IntegerField(required=False)
    submitted = serializers.IntegerField(required=False)


class ReviewerAssignmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    stage_id = serializers.IntegerField()
    state = serializers.CharField()
    application = serializers.DictField()
    scores = serializers.DictField(allow_null=True)
    allowed_actions = serializers.ListField(child=serializers.CharField())


class ReviewerWorkspaceSerializer(serializers.Serializer):
    stage = ReviewerStageSerializer()
    assignments = ReviewerAssignmentSerializer(many=True)
