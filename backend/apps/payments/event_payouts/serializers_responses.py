"""Exact paginated/detail/reference schemas for the permanent core surface."""
from rest_framework import serializers
from .serializers import Integer, PayoutSummarySerializer, PayoutResultSerializer
from .serializers_snapshot import DecisionSummarySerializer


class PayeeProjection(serializers.Serializer):
    state = serializers.CharField()
    id = serializers.UUIDField(required=False)
    version = Integer(required=False)
    country = serializers.CharField(required=False)
    method = serializers.CharField(required=False)
    template_key = serializers.CharField(required=False)
    template_version = Integer(required=False)
    masked_details = serializers.CharField(required=False)
    verified = serializers.BooleanField(required=False)
    purge_due_at = serializers.DateTimeField(required=False, allow_null=True)


class PayoutPage(serializers.Serializer):
    count = Integer()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PayoutSummarySerializer(many=True)


class PayoutEntrySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    amount_minor = Integer()
    currency = serializers.CharField()
    method = serializers.CharField()
    reference = serializers.CharField()
    paid_at = serializers.DateTimeField()
    amends_id = serializers.UUIDField(allow_null=True)
    is_void = serializers.BooleanField()
    payee_revision_id = serializers.UUIDField(required=False, allow_null=True)
    recorded_at = serializers.DateTimeField(required=False)
    recorded_by_id = Integer(required=False)


class ObligationRevisionSerializer(serializers.Serializer):
    id = Integer()
    sequence = Integer()
    kind = serializers.CharField()
    approved_minor = Integer()
    reason_code = serializers.CharField()
    cancellation_note = serializers.CharField()
    decision_summary = DecisionSummarySerializer()
    created_at = serializers.DateTimeField()


class MemberPayoutDetail(PayoutSummarySerializer):
    payee = PayeeProjection()
    entries = PayoutEntrySerializer(many=True)


class FinancePayoutDetail(MemberPayoutDetail):
    revisions = ObligationRevisionSerializer(many=True)
    holds = serializers.ListField(child=serializers.DictField())
    eligibility_history = serializers.ListField(child=serializers.DictField())


class TemplateField(serializers.Serializer):
    key = serializers.CharField()
    required = serializers.BooleanField()
    label = serializers.CharField(help_text="Translated display label for the field.")
    help = serializers.CharField(allow_blank=True, help_text="Optional translated hint; empty when none.")


class PayeeTemplate(serializers.Serializer):
    country = serializers.CharField()
    method = serializers.CharField()
    template_key = serializers.CharField()
    template_version = Integer()
    fields = TemplateField(many=True)
    routing_document_required = serializers.BooleanField()


class OwnerPayeeContext(serializers.Serializer):
    payee = PayeeProjection()
    templates = serializers.ListField(child=serializers.ListField())
    routing_document_methods = serializers.ListField(child=serializers.ListField())
    template_definitions = PayeeTemplate(many=True)
    disclosure_version = Integer()
    disclosure = serializers.CharField()


class ExportPreviewRow(serializers.Serializer):
    batch_id = serializers.UUIDField()
    obligation_id = serializers.UUIDField()
    currency = serializers.CharField()
    remaining_minor = Integer()
    masked_payee = serializers.CharField()
    event_id = serializers.CharField()
    event_title = serializers.CharField()
    participant_reference = serializers.CharField()
    country = serializers.CharField()
    method = serializers.CharField()
    approved_minor = Integer()
    effective_paid_minor = Integer()
    payee_revision = serializers.UUIDField()
    claim_reference = serializers.UUIDField()
    decision_reference = serializers.CharField()
    exported_at = serializers.DateTimeField()


class MaskedPayoutBatchDetail(serializers.Serializer):
    id = serializers.UUIDField()
    expires_at = serializers.DateTimeField()
    preview = ExportPreviewRow(many=True, required=False)


class CurrencyDashboard(serializers.Serializer):
    currency = serializers.CharField()
    approved_minor = Integer()
    paid_minor = Integer()
    approved_unpaid_minor = Integer()
    part_paid_remaining_minor = Integer()
    held_remaining_minor = Integer()
    ageing_0_7_minor = Integer()
    ageing_8_30_minor = Integer()
    ageing_31_plus_minor = Integer()


class FinanceDashboard(serializers.Serializer):
    currencies = CurrencyDashboard(many=True)
    budget_snapshot = serializers.JSONField(allow_null=True)


class EligibilityResult(PayoutResultSerializer):
    eligibility_revision = Integer()
