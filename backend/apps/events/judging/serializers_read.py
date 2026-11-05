"""Closed response serializers shared by schema generation and actual HTTP reads."""

from rest_framework import serializers

from .models_definitions import HackathonPrize, HackathonTrack
from .serializers import ClosedSerializer, CommandInput, CriterionInput, IdList, ResultEnvelope


class TrackRead(serializers.ModelSerializer):
    allowed_actions = serializers.SerializerMethodField()

    def get_allowed_actions(self, obj):
        return ["edit"]

    class Meta:
        model = HackathonTrack
        fields = ("id", "event_id", "version", "allowed_actions", "name", "description", "website_section_id",
                  "criteria", "form", "capacity", "eligibility_rules", "order")


class PrizeRead(TrackRead):
    class Meta:
        model = HackathonPrize
        fields = ("id", "event_id", "version", "allowed_actions", "name", "description", "website_section_id",
                  "track_id", "sponsor_id", "criteria", "form", "eligibility_rules", "order", "award_count", "winner_selection_mode",
                  "amount_per_winner", "kind", "value_text", "estimated_value", "funding")


class CalculationRow(ClosedSerializer):
    snapshot_id = serializers.IntegerField()
    n = serializers.IntegerField()
    rank = serializers.IntegerField()
    score = serializers.CharField(allow_null=True)
    raw_score = serializers.CharField(allow_null=True, required=False)
    zscore = serializers.CharField(allow_null=True, required=False)
    sigma = serializers.CharField(required=False, help_text="Pairwise rounds only: CrowdBT standard deviation.")
    coverage_complete = serializers.BooleanField()
    criterion_averages = serializers.DictField(child=serializers.CharField(), required=False)
    distribution = serializers.DictField(child=serializers.IntegerField(), required=False)
    warnings = serializers.ListField(child=serializers.CharField())


class CalculationRead(ClosedSerializer):
    algorithm_version = serializers.CharField()
    coverage_complete = serializers.BooleanField()
    rows = CalculationRow(many=True)


class RoundRead(ResultEnvelope, CalculationRead):
    mode = serializers.CharField()
    key = serializers.CharField()
    min_reviews = serializers.IntegerField()
    normalization = serializers.CharField()
    minutes_per_view = serializers.IntegerField()
    judging_minutes = serializers.IntegerField()
    estimated_judges = serializers.IntegerField()
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    criteria = CriterionInput(many=True)
    assigned = serializers.IntegerField()
    submitted = serializers.IntegerField()
    recused = serializers.IntegerField()
    guidance = serializers.CharField(allow_blank=True, required=False)
    exploration = serializers.FloatField(allow_null=True, required=False)
    skipped = serializers.IntegerField()
    visibility = serializers.CharField(required=False)
    fresh_eyes = serializers.BooleanField(required=False)
    panel = IdList(required=False)
    advanced_from_id = serializers.IntegerField(allow_null=True, required=False)
    submission_stage_id = serializers.IntegerField(allow_null=True, required=False)
    share_feedback = serializers.BooleanField(required=False)
    judge_reminders = serializers.BooleanField(required=False)


class AssignmentRead(ResultEnvelope):
    round_id = serializers.IntegerField()
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    mode = serializers.CharField()
    batch = serializers.CharField()
    configuration = serializers.DictField()
    scores = serializers.DictField(child=serializers.IntegerField())
    notes = serializers.CharField()
    asset_ids = IdList(required=False)
    batch_projects = serializers.ListField(child=serializers.DictField())
    answers = serializers.ListField(child=serializers.DictField(), required=False,
                                    help_text="S7: the stage's custom answers a judge may read ({label, value}).")
    team_feedback = serializers.CharField(required=False, allow_blank=True)
    share_feedback = serializers.BooleanField(required=False, help_text="S4: whether this round releases team feedback.")


class ConsentRead(ClosedSerializer):
    id = serializers.IntegerField()
    sponsor_id = serializers.IntegerField()
    sponsor_name = serializers.CharField()
    asset_id = serializers.IntegerField()
    purpose = serializers.ChoiceField(choices=("recruiting",))
    state = serializers.ChoiceField(choices=("granted", "revoked"))
    version = serializers.IntegerField()
    consented_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)


class PreviewInput(CommandInput):
    round_ids = IdList(allow_empty=False)


class ResultRead(ResultEnvelope):
    content_sha256 = serializers.CharField(required=False)
    aggregates = serializers.DictField(required=False)
    result_revision_id = serializers.IntegerField(required=False)
    sponsor_proposals = serializers.ListField(child=serializers.DictField(), required=False)


class PreviewRead(ClosedSerializer):
    event_id = serializers.IntegerField()
    algorithm_version = serializers.CharField()
    rounds = serializers.ListField(child=serializers.DictField())


class SponsorSubmissionRead(ClosedSerializer):
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    track_ids = IdList()
    asset_ids = IdList()
    links = serializers.ListField(child=serializers.DictField())
    resumes = serializers.ListField(child=serializers.DictField())


class AssignmentPlanRead(ResultEnvelope):
    pairs = serializers.ListField(child=serializers.DictField(child=serializers.IntegerField()))
    deficits = serializers.DictField(child=serializers.IntegerField())
    loads = serializers.DictField(child=serializers.IntegerField())
    coverage_complete = serializers.BooleanField()
    strategy = serializers.CharField(required=False)
    seed = serializers.CharField(required=False)


class ConsentCommandRead(ResultEnvelope):
    sponsor_id = serializers.IntegerField(required=False)
    asset_id = serializers.IntegerField(required=False)
    purpose = serializers.ChoiceField(choices=("recruiting",), required=False)
    revoked_at = serializers.DateTimeField(allow_null=True, required=False)


class PageBase(ClosedSerializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)


class SponsorOptionRead(ClosedSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    disclosure_revision = serializers.IntegerField()


class ConsentPage(PageBase):
    results = ConsentRead(many=True)
    sponsors = SponsorOptionRead(many=True)


class SponsorPrizeOptionRead(ClosedSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    version = serializers.IntegerField()


class SponsorSubmissionPage(PageBase):
    results = SponsorSubmissionRead(many=True)
    prizes = SponsorPrizeOptionRead(many=True)
