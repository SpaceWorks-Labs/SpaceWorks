"""OpenAPI version-one decision schema, matching G1's closed evidence vocabulary."""
from rest_framework import serializers
from .serializers import Integer, Currency


class Source(serializers.Serializer):
    claim_uuid = serializers.UUIDField()
    claim_revision = Integer(min_value=1)
    decision_uuid = serializers.UUIDField()
    decision_sequence = Integer(min_value=1)


class Decision(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=("approved", "partially_approved", "rejected"))
    decided_at = serializers.DateTimeField()
    actor_id = Integer(min_value=1, allow_null=True)
    reason_code = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)


class CategoryCaps(serializers.Serializer):
    rail = Integer(min_value=0, required=False)
    air = Integer(min_value=0, required=False)
    bus = Integer(min_value=0, required=False)
    ground_transport = Integer(min_value=0, required=False)
    lodging = Integer(min_value=0, required=False)


class AppliedRules(serializers.Serializer):
    category_caps = CategoryCaps()


class Award(serializers.Serializer):
    uuid = serializers.UUIDField()
    cap_minor = Integer(min_value=1)
    currency = Currency()
    policy_revision = Integer(min_value=1)
    rule_revision = Integer(min_value=1)
    applied_rules = AppliedRules()


class Totals(serializers.Serializer):
    claimed_minor = Integer(min_value=0)
    eligible_minor = Integer(min_value=0)
    approved_minor = Integer(min_value=0)


class OverrideAllocation(serializers.Serializer):
    claim_uuid = serializers.UUIDField()
    line_uuid = serializers.UUIDField()
    original_amount_minor = Integer(min_value=1)


class Receipt(serializers.Serializer):
    attachment_id = Integer(min_value=1)
    generation = Integer(min_value=1)
    sha256 = serializers.RegexField(r"^[a-f0-9]{64}$")
    total_minor = Integer(min_value=1)
    currency = Currency()
    receipt_use_id = Integer(min_value=1)
    receipt_use_version = Integer(min_value=1)
    allocation_minor = Integer(min_value=1)
    override_uuid = serializers.UUIDField(allow_null=True)
    override_allocation = OverrideAllocation(many=True)
    override_reason_code = serializers.CharField(allow_blank=True)
    override_reason = serializers.CharField(allow_blank=True)


class Limits(serializers.Serializer):
    cap_minor = Integer(min_value=0)


class DecisionLine(serializers.Serializer):
    line_uuid = serializers.UUIDField()
    category = serializers.ChoiceField(choices=("rail", "air", "bus", "ground_transport", "lodging"))
    expense_date = serializers.DateField()
    vendor = serializers.CharField()
    description = serializers.CharField()
    traveller = serializers.CharField()
    original_amount_minor = Integer(min_value=0)
    original_currency = Currency()
    original_exponent = Integer(min_value=0)
    fx_rate = serializers.CharField()
    rate_date = serializers.DateField()
    rate_source = serializers.CharField()
    source_note = serializers.CharField(allow_blank=True)
    currency = Currency()
    target_exponent = Integer(min_value=0)
    converted_minor = Integer(min_value=0)
    approved_minor = Integer(min_value=0)
    limits = Limits()
    rounding = serializers.ChoiceField(choices=("HALF_UP",))
    reason_code = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)
    receipt = Receipt()


class EligibilityEvidence(serializers.Serializer):
    registration_id = Integer(allow_null=True)
    attendance_revision = Integer(allow_null=True)
    checkin_event_id = Integer(allow_null=True)
    correction_watermark = Integer(allow_null=True)
    attestation_uuid = serializers.UUIDField(allow_null=True)
    project_snapshot_ref = serializers.UUIDField(allow_null=True)
    core_eligibility_revision = Integer(allow_null=True)


class DecisionSummarySerializer(serializers.Serializer):
    schema_version = Integer(min_value=1, max_value=1)
    source = Source()
    decision = Decision()
    award = Award()
    totals = Totals()
    lines = DecisionLine(many=True)
    eligibility = EligibilityEvidence()
