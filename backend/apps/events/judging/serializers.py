"""Closed domain inputs. Unknown members never become dynamic model assignments."""

from collections.abc import Mapping
from decimal import Decimal

from rest_framework import serializers


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping) and set(data) - set(self.fields):
            raise serializers.ValidationError({key: ["Unknown field."] for key in set(data) - set(self.fields)})
        return super().to_internal_value(data)


class CommandInput(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)

    def validate_expected_version(self, value):
        if type(self.initial_data.get("expected_version")) is not int:
            raise serializers.ValidationError("Use an integer version.")
        return value


class IdList(serializers.ListField):
    def __init__(self, **kwargs):
        super().__init__(child=serializers.IntegerField(min_value=1), max_length=2000, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, list) and any(type(value) is not int for value in data):
            raise serializers.ValidationError("Use integer IDs.")
        result = super().to_internal_value(data)
        if len(set(result)) != len(result):
            raise serializers.ValidationError("Duplicate IDs are not allowed.")
        return result


class TrackInput(CommandInput):
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=4000, allow_blank=True, required=False)
    website_section_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    criteria = serializers.DictField(child=serializers.CharField(max_length=2000), required=False)
    form = serializers.JSONField(required=False)
    capacity = serializers.IntegerField(min_value=0, max_value=100000, required=False)
    eligibility_rules = serializers.DictField(child=serializers.ListField(child=serializers.CharField(max_length=64),
                                                                         max_length=30), required=False)
    order = serializers.IntegerField(min_value=0, max_value=10000, required=False)

    def validate_criteria(self, value):
        if len(value) > 30 or any(len(key) > 64 for key in value):
            raise serializers.ValidationError("Use at most 30 short criterion keys.")
        return value

    def validate_eligibility_rules(self, value):
        if set(value) - {"required_tech_tags"}:
            raise serializers.ValidationError("Only required_tech_tags is supported; age gating is forbidden.")
        return value

    def validate_form(self, value):
        from apps.forms_schema.validation import validate_form_schema
        from django.core.exceptions import ValidationError
        try:
            return validate_form_schema(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class PrizeInput(TrackInput):
    capacity = None
    amount_per_winner = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
                                                 allow_null=True, required=False)
    track_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    sponsor_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    award_count = serializers.IntegerField(min_value=1, max_value=100, required=False)
    winner_selection_mode = serializers.ChoiceField(choices=("manager", "sponsor_proposal"), required=False)
    # Hack-money G5/G8: non-cash prizes and prizes the sponsor pays the winner directly.
    kind = serializers.ChoiceField(choices=("cash", "item", "credit", "perk"), required=False)
    value_text = serializers.CharField(max_length=300, allow_blank=True, required=False,
                                       help_text="What a non-cash prize is, e.g. 'Raspberry Pi 5 kit per member'.")
    estimated_value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
                                               allow_null=True, required=False)
    funding = serializers.ChoiceField(choices=("space", "sponsor_direct"), required=False,
                                      help_text="sponsor_direct: the sponsor pays the winner; the space records "
                                                "fulfilment only, never an expense.")


class CriterionInput(ClosedSerializer):
    key = serializers.RegexField(r"^[a-z][a-z0-9_-]{0,63}$")
    label = serializers.CharField(max_length=160)
    weight = serializers.DecimalField(max_digits=10, decimal_places=4, min_value=Decimal("0.0001"))
    anchors = serializers.DictField(child=serializers.CharField(max_length=500))

    def validate_anchors(self, value):
        if set(value) != {"1", "2", "3", "4", "5"}:
            raise serializers.ValidationError("Provide an anchor for every score from 1 to 5.")
        return value


class RoundInput(CommandInput):
    key = serializers.SlugField(max_length=64)
    mode = serializers.ChoiceField(choices=("weighted_1_5", "top3", "pairwise"))
    min_reviews = serializers.IntegerField(min_value=3, max_value=20, required=False)
    normalization = serializers.ChoiceField(choices=("none", "zscore"), required=False)
    minutes_per_view = serializers.IntegerField(min_value=1, max_value=120, required=False)
    judging_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    opens_at = serializers.DateTimeField(allow_null=True, required=False)
    closes_at = serializers.DateTimeField(allow_null=True, required=False)
    criteria = CriterionInput(many=True, required=False, allow_empty=False, max_length=30)
    guidance = serializers.CharField(max_length=500, allow_blank=True, required=False,
                                     help_text="Pairwise only: what 'better' means for judges.")
    exploration = serializers.DecimalField(max_digits=3, decimal_places=2, min_value=Decimal("0"),
                                           max_value=Decimal("0.30"), required=False,
                                           help_text="Pairwise only: share of picks made at random among projects still needing coverage.")
    visibility = serializers.ChoiceField(choices=("assigned", "all"), required=False)  # L21b round settings
    fresh_eyes = serializers.BooleanField(required=False)
    panel = IdList(required=False, help_text="Judge role assignment IDs; empty means every active judge.")

    def validate_criteria(self, value):
        if len({row["key"] for row in value}) != len(value):
            raise serializers.ValidationError("Criterion keys must be distinct.")
        return value


class AssignInput(CommandInput):
    strategy = serializers.ChoiceField(choices=("balanced", "track", "room", "random"), default="balanced")
    judge_role_assignment_ids = IdList(allow_empty=False)
    max_load = serializers.IntegerField(min_value=1, max_value=2000, default=100)
    seed = serializers.CharField(max_length=64, default="0")
    dry_run = serializers.BooleanField(default=False)


class FinalizeRoundInput(CommandInput):
    coverage_exception_reason = serializers.CharField(max_length=2000, required=False, allow_blank=False)


class ScoreInput(CommandInput):
    scores = serializers.DictField(child=serializers.IntegerField(min_value=1, max_value=5), required=False)
    notes = serializers.CharField(max_length=4000, allow_blank=True, default="")
    submit = serializers.BooleanField(default=True)

    def validate_scores(self, value):
        # DRF IntegerField accepts 1.0 and true; the domain contract requires integers.
        original = self.initial_data.get("scores", {})
        if any(type(item) is not int for item in original.values()):
            raise serializers.ValidationError("Use integer scores from 1 to 5.")
        return value


class RankInput(CommandInput):
    ordered_top3 = IdList(allow_empty=False)


class ReasonInput(CommandInput):
    reason = serializers.CharField(max_length=2000)


class AwardInput(ClosedSerializer):
    prize_id = serializers.IntegerField(min_value=1)
    snapshot_id = serializers.IntegerField(min_value=1)
    rank = serializers.IntegerField(min_value=1, max_value=100)
    public_requested = serializers.BooleanField(default=False)
    tie_reason = serializers.CharField(max_length=2000, required=False)


class ResultsInput(CommandInput):
    round_ids = IdList(allow_empty=False)
    awards = AwardInput(many=True, default=list, max_length=1000)
    integrity_reviewed = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=2000, required=False)


class PublishResultInput(CommandInput):
    result_revision_id = serializers.IntegerField(min_value=1)


class SponsorGrantInput(CommandInput):
    sponsor_id = serializers.IntegerField(min_value=1)
    asset_id = serializers.IntegerField(min_value=1)
    purpose = serializers.CharField(max_length=16)
    consent = serializers.BooleanField()
    disclosure_revision = serializers.IntegerField(min_value=1)

    def validate_consent(self, value):
        if value is not True or self.initial_data.get("consent") is not True:
            from .errors import ProgrammeError
            raise ProgrammeError("explicit_consent_required", "Explicit consent is required.", status=400)
        return value

    def validate_purpose(self, value):
        if value != "recruiting":
            from .errors import ProgrammeError
            raise ProgrammeError("invalid_purpose", "Choose recruiting consent.", status=400)
        return value


class SponsorProposalInput(CommandInput):
    snapshot_id = serializers.IntegerField(min_value=1)


class ResultEnvelope(ClosedSerializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField(required=False)
    allowed_actions = serializers.ListField(child=serializers.CharField())


def validated(serializer, data, *, partial=False):
    value = serializer(data=data, partial=partial)
    value.is_valid(raise_exception=True)
    # PATCH is partial in domain fields only; command identity is ALWAYS required.
    for key in ("operation_id", "expected_version"):
        if key not in value.validated_data:
            raise serializers.ValidationError({key: "This field is required."})
    return value.validated_data
