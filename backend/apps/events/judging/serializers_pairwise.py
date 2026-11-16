"""Closed pairwise inputs and response shapes. `expected_version` is the judge's cursor version."""

from rest_framework import serializers

from .serializers import ClosedSerializer, CommandInput


class CompareInput(CommandInput):
    outcome = serializers.ChoiceField(choices=(("previous", "The one before was better"), ("current", "This one is better")))
    notes = serializers.CharField(max_length=2000, allow_blank=True, default="")


class SkipInput(CommandInput):
    notes = serializers.CharField(max_length=2000, allow_blank=True, default="")


class PairwiseCard(ClosedSerializer):
    assignment_id = serializers.IntegerField()
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    track_id = serializers.IntegerField(allow_null=True)
    asset_ids = serializers.ListField(child=serializers.IntegerField())


class PairwiseStateRead(ClosedSerializer):
    round_id = serializers.IntegerField()
    round_key = serializers.CharField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField(help_text="Cursor version; send it as expected_version.")
    guidance = serializers.CharField(allow_blank=True)
    previous = PairwiseCard(allow_null=True)
    current = PairwiseCard(allow_null=True)
    compared = serializers.IntegerField()
    remaining = serializers.IntegerField()
    finished = serializers.BooleanField()
    allowed_actions = serializers.ListField(child=serializers.ChoiceField(choices=("next", "compare", "skip", "recuse")))


class PairwiseRow(ClosedSerializer):
    snapshot_id = serializers.IntegerField()
    n = serializers.IntegerField(help_text="Valid decisive comparisons that include this project.")
    rank = serializers.IntegerField()
    score = serializers.CharField(allow_null=True, help_text="CrowdBT mean quality mu, four decimals.")
    sigma = serializers.CharField(help_text="CrowdBT standard deviation, four decimals.")
    coverage_complete = serializers.BooleanField()
    warnings = serializers.ListField(child=serializers.CharField())


class PairwiseJudgeCoverage(ClosedSerializer):
    judge_role_assignment_id = serializers.IntegerField()
    compared = serializers.IntegerField()
    skipped = serializers.IntegerField()


class PairwiseStandingsRead(ClosedSerializer):
    round_id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    algorithm_version = serializers.CharField()
    coverage_complete = serializers.BooleanField()
    rows = PairwiseRow(many=True)
    judges = PairwiseJudgeCoverage(many=True)


class PairwiseCommandResult(ClosedSerializer):
    id = serializers.IntegerField(allow_null=True)
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    round_id = serializers.IntegerField()
    allowed_actions = serializers.ListField(child=serializers.CharField())
