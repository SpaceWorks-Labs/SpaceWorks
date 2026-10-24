"""Typed bootstrap for the receiving project editor; form JSON belongs to F."""
from rest_framework import serializers


class ProjectBudgetSerializer(serializers.Serializer):
    limit_bytes = serializers.IntegerField(allow_null=True)
    used_bytes = serializers.IntegerField()
    reserved_bytes = serializers.IntegerField()
    remaining_bytes = serializers.IntegerField(allow_null=True)


class ProjectSlotSerializer(serializers.Serializer):
    group = serializers.CharField()
    max_bytes = serializers.IntegerField()


class ProjectTrackSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    version = serializers.IntegerField()
    form = serializers.JSONField()
    criteria = serializers.DictField()


class ProjectPrizeSerializer(ProjectTrackSerializer):
    track_id = serializers.IntegerField(allow_null=True)


class ProjectUploadPolicySerializer(serializers.Serializer):
    name = serializers.CharField()
    version = serializers.IntegerField()


class ProjectRequirementsSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    deadline = serializers.DateTimeField()
    opens_at = serializers.DateTimeField(allow_null=True)
    grace_seconds = serializers.IntegerField()
    late_policy = serializers.ChoiceField(choices=("reject", "accept_flagged"))
    upload_policy = ProjectUploadPolicySerializer()
    budget = ProjectBudgetSerializer()
    slots = ProjectSlotSerializer(many=True)
    tracks = ProjectTrackSerializer(many=True)
    prizes = ProjectPrizeSerializer(many=True)
