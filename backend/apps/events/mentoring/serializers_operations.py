from rest_framework import serializers
from apps.events.contributions.serializers import CommandSerializer, StrictSerializer


class DistributionSerializer(serializers.Serializer):
    n = serializers.IntegerField()
    average_seconds = serializers.FloatField(allow_null=True)
    median_seconds = serializers.FloatField(allow_null=True)
    p90_seconds = serializers.IntegerField(allow_null=True)


class RoundProgressSerializer(serializers.Serializer):
    round_id = serializers.IntegerField()
    completed = serializers.IntegerField()
    remaining = serializers.IntegerField(allow_null=True)


class AttentionSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=["away_twice"])
    count = serializers.IntegerField()


class NudgeSerializer(serializers.Serializer):
    mentor_assignment_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=["quiet", "long_visit", "check_in_due"])
    minutes = serializers.IntegerField()


class GenerositySerializer(serializers.Serializer):
    mentor_assignment_id = serializers.IntegerField()
    n = serializers.IntegerField()
    mean = serializers.FloatField(allow_null=True)
    z_score = serializers.FloatField(allow_null=True)


class AnalyticsSerializer(serializers.Serializer):
    completed_checkins = serializers.IntegerField()
    open_help = serializers.IntegerField()
    first_response = DistributionSerializer()
    help_duration = DistributionSerializer()
    visit_duration = DistributionSerializer()
    expired_leases = serializers.IntegerField()
    scope = serializers.ChoiceField(choices=["own", "event"])
    per_round = RoundProgressSerializer(many=True)
    active_mentors = serializers.IntegerField()
    attention = AttentionSerializer(many=True)
    nudges = NudgeSerializer(many=True)
    generosity = GenerositySerializer(many=True)
    attention_preference = serializers.DictField()


class ImportRowSerializer(StrictSerializer):
    team_id = serializers.IntegerField(min_value=1)
    member_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=50)
    alias = serializers.CharField(max_length=100)


class ImportPreviewSerializer(CommandSerializer):
    rows = ImportRowSerializer(many=True, min_length=1, max_length=500)
    practice_run_id = serializers.UUIDField(allow_null=True, required=False)


class ImportUploadSerializer(CommandSerializer):
    file = serializers.FileField()
    practice_run_id = serializers.UUIDField(allow_null=True, required=False)


class ImportCommitSerializer(CommandSerializer):
    preview_token = serializers.UUIDField()
    mapping_sha256 = serializers.RegexField(r"^[a-f0-9]{64}$")


class ImportResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    preview_token = serializers.UUIDField()
    mapping_sha256 = serializers.CharField()
    expires_at = serializers.DateTimeField()
    state = serializers.ChoiceField(choices=["preview", "committed"])
    allowed_actions = serializers.ListField(child=serializers.CharField())
    practice_run_id = serializers.UUIDField(allow_null=True)
    mapping_count = serializers.IntegerField()
