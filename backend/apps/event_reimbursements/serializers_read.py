"""Document private projections without giving metadata reviewers a finance schema."""
from rest_framework import serializers as s
from drf_spectacular.utils import extend_schema_serializer
from .serializers_request import Estimate
from .serializers_finance import PolicySettings


class PoolDetail(s.Serializer):
    audience = s.ChoiceField(choices=("participants", "crew"), help_text="Hack-money G14: crew awards use the crew pool.")
    id = s.IntegerField()
    version = s.IntegerField()
    currency = s.CharField()
    total_minor = s.IntegerField()
    reserved_minor = s.IntegerField()
    committed_minor = s.IntegerField()
    available_minor = s.IntegerField()


class ProgrammeDetail(PolicySettings):
    initialized = s.BooleanField()
    imported_paused = s.BooleanField(required=False)
    id = s.IntegerField(required=False)
    version = s.IntegerField(required=False)
    currency = s.CharField(required=False)
    finance_policy_revision = s.IntegerField(required=False)


class ProgrammeFinanceDetail(ProgrammeDetail):
    pools = PoolDetail(many=True, required=False)


class AwardDetail(s.Serializer):
    id = s.IntegerField()
    uuid = s.UUIDField()
    version = s.IntegerField()
    state = s.CharField()
    amount_minor = s.IntegerField()
    currency = s.CharField()
    accept_by = s.DateTimeField()
    due_revision = s.IntegerField()
    award_revision = s.IntegerField()
    rule_revision = s.IntegerField()
    calculation_snapshot = s.DictField()
    accepted_at = s.DateTimeField(allow_null=True)
    reason_code = s.CharField()


class BudgetPreview(s.Serializer):
    pool_id = s.IntegerField()
    pool_version = s.IntegerField()
    available_minor = s.IntegerField()


class RequestDetail(s.Serializer):
    id = s.IntegerField()
    uuid = s.UUIDField()
    version = s.IntegerField()
    state = s.CharField()
    member_id = s.IntegerField()
    currency = s.CharField()
    estimated_total_minor = s.IntegerField()
    category_estimates = Estimate(many=True)
    submitted_at = s.DateTimeField(allow_null=True)
    reason_code = s.CharField()
    budget = BudgetPreview(required=False)
    award = AwardDetail(required=False, allow_null=True)


class PrivateRequestDetail(RequestDetail):
    itinerary = s.DictField()
    need_statement = s.CharField()
    distance_km = s.CharField(allow_null=True)
    reason = s.CharField()


@extend_schema_serializer(component_name="ReimbursementPayoutSummary")
class PayoutSummary(s.Serializer):
    id = s.UUIDField()
    version = s.IntegerField()
    event_id = s.IntegerField()
    event_title = s.CharField()
    currency = s.CharField()
    approved_minor = s.IntegerField()
    effective_paid_minor = s.IntegerField()
    remaining_minor = s.IntegerField()
    state = s.CharField()
    eligibility_status = s.CharField()
    eligibility_revision = s.IntegerField()
    current_revision_sequence = s.IntegerField(allow_null=True)
    coordination_state = s.CharField()


class ReceiptReferenceDetail(s.Serializer):
    asset_id = s.IntegerField()
    sha256 = s.CharField()
    generation = s.IntegerField()
    state = s.CharField()


class LineDetail(s.Serializer):
    line_uuid = s.UUIDField()
    category = s.CharField()
    vendor = s.CharField()
    description = s.CharField()
    traveller = s.CharField()
    expense_date = s.DateField()
    original_amount_minor = s.IntegerField()
    original_currency = s.CharField()
    fx_rate = s.CharField()
    rate_date = s.DateField()
    rate_source = s.CharField()
    source_note = s.CharField()
    converted_minor = s.IntegerField()
    route = s.DictField()
    lodging_starts_on = s.DateField(allow_null=True)
    lodging_ends_on = s.DateField(allow_null=True)
    lodging_nights = s.IntegerField(allow_null=True)
    receipt = ReceiptReferenceDetail()


class RevisionDetail(s.Serializer):
    id = s.IntegerField()
    revision = s.IntegerField()
    submitted_at = s.DateTimeField()
    currency = s.CharField()
    total_minor = s.IntegerField()
    lines = LineDetail(many=True)


class LineDecisionDetail(s.Serializer):
    line_uuid = s.UUIDField()
    approved_minor = s.IntegerField()
    reason_code = s.CharField()
    reason = s.CharField()


class DecisionDetail(s.Serializer):
    id = s.IntegerField()
    sequence = s.IntegerField()
    outcome = s.CharField()
    approved_total_minor = s.IntegerField()
    currency = s.CharField()
    reason_code = s.CharField()
    reason = s.CharField()
    decided_at = s.DateTimeField()
    lines = LineDecisionDetail(many=True)


class ScreeningReceipt(s.Serializer):
    line_uuid = s.UUIDField()
    category = s.CharField()
    converted_minor = s.IntegerField()
    receipt_present = s.BooleanField()
    sha256 = s.CharField()


class ClaimSummary(s.Serializer):
    id = s.IntegerField()
    uuid = s.UUIDField()
    version = s.IntegerField()
    state = s.CharField()
    display_state = s.CharField()
    member_id = s.IntegerField()
    award_id = s.IntegerField()
    current_revision = s.IntegerField(allow_null=True)
    current_decision = s.IntegerField(allow_null=True)
    effective_due_at = s.DateTimeField()
    info_due_at = s.DateTimeField(allow_null=True)
    due_revision = s.IntegerField()
    appeal_due_at = s.DateTimeField(allow_null=True)
    appeal_used = s.BooleanField()
    domain_closed_at = s.DateTimeField(allow_null=True)
    allowed_actions = s.ListField(child=s.CharField())
    payout = PayoutSummary(allow_null=True)


class ClaimScreeningDetail(ClaimSummary):
    receipt_metadata = ScreeningReceipt(many=True, required=False)


class ClaimFinanceDetail(ClaimSummary):
    draft = s.DictField(allow_null=True)
    revisions = RevisionDetail(many=True)
    decisions = DecisionDetail(many=True)


class RequestContext(s.Serializer):
    programme_id = s.IntegerField()
    programme_version = s.IntegerField()
    form = s.DictField()
    schema = s.DictField()


class MemberSummary(s.Serializer):
    available = s.BooleanField()
    programme = ProgrammeDetail()
    request_context = RequestContext(allow_null=True)
    request = PrivateRequestDetail(allow_null=True)
    award = AwardDetail(allow_null=True)
    claim = ClaimFinanceDetail(allow_null=True)
    allowed_actions = s.ListField(child=s.CharField())


class RequestPage(s.Serializer):
    count = s.IntegerField()
    next = s.URLField(allow_null=True)
    previous = s.URLField(allow_null=True)
    results = RequestDetail(many=True)


class FinanceRequestPage(RequestPage):
    results = PrivateRequestDetail(many=True)


class ClaimPage(s.Serializer):
    count = s.IntegerField()
    next = s.URLField(allow_null=True)
    previous = s.URLField(allow_null=True)
    results = ClaimSummary(many=True)
