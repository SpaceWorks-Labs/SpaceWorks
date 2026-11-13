"""Explicit finance variants; recommendations never select the decision writer."""
from rest_framework import serializers as s
from .serializers import Command
from .serializers_request import ClosedSerializer, StrictInteger, Currency
from apps.payments.event_payouts.validation import MAX_MINOR

REASONS = ("approved", "policy_cap", "category_cap", "ineligible", "insufficient_evidence", "receipt_mismatch",
    "attendance_required", "need_based", "tier_award", "budget_available", "waitlisted", "declined",
    "information_required", "deadline_extension", "attendance_exception", "receipt_shared", "decision_correction",
    "no_liability", "other")


class PolicySettings(ClosedSerializer):
    enabled = s.BooleanField(required=False)
    request_phase = s.ChoiceField(choices=("application", "after_acceptance", "both"), required=False)
    request_opens_at = s.DateTimeField(required=False, allow_null=True)
    request_closes_at = s.DateTimeField(required=False, allow_null=True)
    award_mode = s.ChoiceField(choices=("fixed_tier", "route_cap", "percentage", "need_based"), required=False)
    tier_rules = s.DictField(required=False)
    allowed_categories = s.ListField(child=s.CharField(), max_length=5, required=False)
    exclusions = s.ListField(child=s.CharField(), max_length=30, required=False)
    min_distance_km = s.DecimalField(max_digits=8, decimal_places=3, min_value=0, max_value=40075, required=False, allow_null=True)
    eligible_countries = s.ListField(child=s.RegexField(r"^[A-Z]{2}$"), max_length=250, required=False)
    eligible_cohorts = s.ListField(child=s.CharField(max_length=64), max_length=250, required=False)
    min_application_stage = StrictInteger(min_value=1, max_value=20, required=False, allow_null=True)
    award_accept_days = StrictInteger(min_value=1, max_value=365, required=False)
    claim_due_at = s.DateTimeField(required=False)
    attendance_required = s.BooleanField(required=False)
    require_project_submission = s.BooleanField(required=False)
    required_submission = s.ChoiceField(choices=("none", "any_stage", "stage", "final_stage", "shortlisted_at", "finalist"),
                                        required=False, help_text="G11: which submission earns the grant.")
    required_submission_stage = StrictInteger(min_value=1, max_value=50, required=False, allow_null=True,
                                              help_text="The stage position for 'stage' and 'shortlisted_at'.")
    permitted_venue_sources = s.ListField(child=s.ChoiceField(choices=("qr", "venue_station", "offline_sync")), required=False)
    category_limits = s.DictField(child=StrictInteger(min_value=0, max_value=MAX_MINOR), required=False)


class ProgrammeCreateOrGetCommand(Command):
    expected_version = StrictInteger(min_value=0, max_value=0)
    currency = Currency()
    initial_total_minor = StrictInteger(min_value=0, max_value=MAX_MINOR)
    initial_settings = PolicySettings()


class ProgrammeFinanceCommand(Command):
    reconciliation_confirmed = s.BooleanField(default=False)
    policy_revision = StrictInteger(min_value=1)
    settings = PolicySettings()
    pool_id = StrictInteger(min_value=1)
    expected_pool_version = StrictInteger(min_value=1)
    budget_delta_minor = StrictInteger(min_value=-MAX_MINOR, max_value=MAX_MINOR)
    reason_code = s.ChoiceField(choices=REASONS)


class AwardDecisionCommand(Command):
    expected_award_version = StrictInteger(min_value=1, allow_null=True)
    expected_pool_version = StrictInteger(min_value=1)
    outcome = s.ChoiceField(choices=("award", "waitlist", "decline"))
    amount_minor = StrictInteger(min_value=1, max_value=MAX_MINOR, required=False)
    currency = Currency(required=False)
    tier = s.CharField(max_length=64, required=False)
    accept_by = s.DateTimeField(required=False)
    reason_code = s.ChoiceField(choices=REASONS)

    def validate(self, value):
        if value["outcome"] == "award" and not {"amount_minor", "currency"} <= value.keys():
            raise s.ValidationError({"code": "award_amount_required"})
        if value["outcome"] != "award" and set(value) & {"amount_minor", "currency", "tier", "accept_by"}:
            raise s.ValidationError({"code": "award_fields_not_allowed"})
        return value


class LineDecision(ClosedSerializer):
    line_uuid = s.UUIDField()
    approved_minor = StrictInteger(min_value=0, max_value=MAX_MINOR)
    reason_code = s.ChoiceField(choices=REASONS)
    reason = s.CharField(max_length=5000, allow_blank=True, default="")


class ClaimRecommendationCommand(Command):
    mode = s.ChoiceField(choices=("recommend",))
    claim_revision_id = StrictInteger(min_value=1)
    recommendation = s.ChoiceField(choices=("approve", "partial", "reject", "request_info"))
    reason_code = s.ChoiceField(choices=REASONS)
    note = s.CharField(max_length=5000, allow_blank=True, default="")


class ClaimDecisionCommand(Command):
    mode = s.ChoiceField(choices=("decide",))
    claim_revision_id = StrictInteger(min_value=1)
    expected_pool_version = StrictInteger(min_value=1)
    expected_decision_sequence = StrictInteger(min_value=0)
    expected_obligation_version = StrictInteger(min_value=1, allow_null=True)
    outcome = s.ChoiceField(choices=("approved", "partially_approved", "rejected", "returned_for_info"))
    line_decisions = LineDecision(many=True, max_length=50)
    eligibility_revision = StrictInteger(min_value=0)
    reason_code = s.ChoiceField(choices=REASONS)
    note = s.CharField(max_length=5000, allow_blank=True, default="")
    info_due_at = s.DateTimeField(required=False)


class ClaimReviewCommand(s.Serializer):
    """OpenAPI uses a oneOf; runtime selects a closed variant before validation."""
    def to_internal_value(self, data):
        target = {"recommend": ClaimRecommendationCommand, "decide": ClaimDecisionCommand}.get(
            data.get("mode") if isinstance(data, dict) else None)
        if target is None:
            raise s.ValidationError({"code": "review_mode_required"})
        serializer = target(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class CorrectClaimDecisionCommand(ClaimDecisionCommand):
    mode = None
    outcome = s.ChoiceField(choices=("approved", "partially_approved", "rejected"))


class ClaimDeadlineCommand(Command):
    due_revision = StrictInteger(min_value=1)
    due_at = s.DateTimeField()
    reason_code = s.ChoiceField(choices=REASONS)
    note = s.CharField(max_length=5000, allow_blank=False)


class AttendanceAttestationCommand(Command):
    registration_id = StrictInteger(min_value=1)
    expected_attendance_revision = StrictInteger(min_value=0)
    attended_at = s.DateTimeField()
    venue_evidence_refs = s.ListField(child=s.RegexField(r"^[A-Za-z0-9:_-]{1,128}$"), max_length=20, allow_empty=False)
    reason_code = s.ChoiceField(choices=REASONS)
    note = s.CharField(max_length=5000, allow_blank=False)


class Allocation(ClosedSerializer):
    claim_uuid = s.UUIDField()
    line_uuid = s.UUIDField()
    original_amount_minor = StrictInteger(min_value=1, max_value=MAX_MINOR)


class ReceiptAllocationOverrideCommand(Command):
    asset_id = StrictInteger(min_value=1)
    expected_receipt_use_version = StrictInteger(min_value=1)
    receipt_total_minor = StrictInteger(min_value=1, max_value=MAX_MINOR)
    original_currency = Currency()
    allocations = Allocation(many=True, allow_empty=False, max_length=100)
    reason_code = s.ChoiceField(choices=REASONS)
    note = s.CharField(max_length=5000, allow_blank=False)
