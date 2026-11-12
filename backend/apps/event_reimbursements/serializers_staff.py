"""Documented staff-console read fields added by the decision 296 review (see ``staff_projection``)."""
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers as s


@extend_schema_serializer(component_name="ReimbursementTier")
class Tier(s.Serializer):
    key = s.CharField()
    label = s.CharField()
    amount_minor = s.IntegerField()


class Recommendation(s.Serializer):
    recommendation = s.CharField()
    reason_code = s.CharField()
    note = s.CharField(allow_blank=True)


class ReviewLine(s.Serializer):
    line_uuid = s.UUIDField()
    category = s.CharField()
    original_amount_minor = s.IntegerField()
    original_currency = s.CharField()
    converted_minor = s.IntegerField()
    receipt_present = s.BooleanField()
    duplicate_receipt = s.BooleanField()
    receipt_use_version = s.IntegerField()
    receipt_asset_id = s.IntegerField(required=False, help_text="Finance only.")
    vendor = s.CharField(required=False, help_text="Finance only.")
    description = s.CharField(required=False, help_text="Finance only.")
    expense_date = s.DateField(required=False, help_text="Finance only.")
    fx_rate = s.CharField(required=False, help_text="Finance only.")


class RequestStaffFields(s.Serializer):
    owner_label = s.CharField(required=False)
    allowed_actions = s.ListField(child=s.CharField(), required=False, help_text="decide: the award decision is open.")
    tiers = Tier(many=True, required=False, help_text="fixed_tier / route_cap policies only.")


class ClaimStaffFields(s.Serializer):
    owner_label = s.CharField(required=False)
    currency = s.CharField(required=False)
    claimed_minor = s.IntegerField(required=False)


class ClaimReviewFields(ClaimStaffFields):
    accepted_cap_minor = s.IntegerField(required=False)
    pool_version = s.IntegerField(required=False)
    decision_sequence = s.IntegerField(required=False)
    decision_reason = s.CharField(required=False, allow_blank=True)
    registration_id = s.IntegerField(required=False, allow_null=True)
    attendance_revision = s.IntegerField(required=False)
    eligibility_revision = s.IntegerField(required=False)
    attendance_eligible = s.BooleanField(required=False)
    recommendations = Recommendation(many=True, required=False)
    appeal_statement = s.CharField(required=False, allow_null=True, help_text="Finance only.")
    review_lines = ReviewLine(many=True, required=False)
