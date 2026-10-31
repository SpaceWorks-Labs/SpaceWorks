"""Offline claims, maker-checker, capture flags and disputes (lane L5)."""

from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import (
    PaymentCaptureFlag, PaymentClaim, PaymentDispute, PaymentDisputeEvent, SettlementConfirmation,
)


class UpiDetailsSerializer(serializers.Serializer):
    vpa = serializers.CharField()
    payee_name = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    reference = serializers.CharField(help_text="Quote this in the UPI note; the claim uses it to match.")
    uri = serializers.CharField(help_text="upi://pay intent for the exact amount; render it as a QR code.")


class OwnClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentClaim
        fields = ("id", "method", "reference", "paid_on", "status", "decision_note", "created_at")
        read_only_fields = fields


class OfflineCollectionSerializer(serializers.Serializer):
    upi = UpiDetailsSerializer(allow_null=True)
    instructions = serializers.CharField(allow_blank=True)
    claim = OwnClaimSerializer(allow_null=True)
    claimable = serializers.BooleanField()


class ClaimSubmitSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64, help_text="The UTR / transaction reference.")
    paid_on = serializers.DateField()
    method = serializers.ChoiceField(choices=PaymentClaim.Method.choices, default=PaymentClaim.Method.UPI)


class StaffClaimSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(read_only=True)
    subject_label = serializers.CharField(source="payment.subject_label", read_only=True)
    via_pay_link = serializers.SerializerMethodField()

    class Meta:
        model = PaymentClaim
        fields = ("id", "payment_id", "subject_label", "method", "reference", "paid_on", "amount", "currency",
                  "status", "decision_note", "decided_at", "created_at", "via_pay_link")
        read_only_fields = fields

    def get_via_pay_link(self, claim) -> bool:
        return claim.pay_link_id is not None


class DecisionNoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ConfirmationSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(read_only=True)
    subject_label = serializers.CharField(source="payment.subject_label", read_only=True)
    proposed_by_me = serializers.SerializerMethodField()
    from_claim = serializers.SerializerMethodField()

    class Meta:
        model = SettlementConfirmation
        fields = ("id", "payment_id", "subject_label", "method", "reference", "received_at", "amount", "currency",
                  "status", "decision_note", "created_at", "decided_at", "proposed_by_me", "from_claim")
        read_only_fields = fields

    def get_proposed_by_me(self, row) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.pk == row.proposed_by_id)

    def get_from_claim(self, row) -> bool:
        return row.claim_id is not None


class CaptureFlagSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(read_only=True)
    subject_label = serializers.CharField(source="payment.subject_label", read_only=True)
    charge_amount = serializers.DecimalField(source="payment.amount", max_digits=12, decimal_places=2, read_only=True)
    charge_currency = serializers.CharField(source="payment.currency", read_only=True)

    class Meta:
        model = PaymentCaptureFlag
        fields = ("id", "payment_id", "subject_label", "kind", "provider", "captured_amount", "captured_currency",
                  "charge_amount", "charge_currency", "prior_status", "flagged_at", "resolution",
                  "resolution_note", "resolved_at", "refund_case")
        read_only_fields = fields


class FlagResolveSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=[
        PaymentCaptureFlag.Resolution.ISSUE_RECEIVED, PaymentCaptureFlag.Resolution.REFUND_CASE,
        PaymentCaptureFlag.Resolution.ACKNOWLEDGED])
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False)


class DisputeEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDisputeEvent
        fields = ("status", "provider_status", "amount", "recorded_at")
        read_only_fields = fields


class DisputeSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(read_only=True)
    subject_label = serializers.CharField(source="payment.subject_label", read_only=True)
    subject_type = serializers.CharField(source="payment.subject_type", read_only=True)

    class Meta:
        model = PaymentDispute
        fields = ("id", "payment_id", "subject_type", "subject_label", "provider", "amount", "currency", "reason",
                  "status", "provider_status", "evidence_due_at", "opened_at", "updated_at")
        read_only_fields = fields


class DisputeDetailSerializer(DisputeSerializer):
    events = DisputeEventSerializer(many=True, read_only=True)

    class Meta(DisputeSerializer.Meta):
        fields = (*DisputeSerializer.Meta.fields, "events")
        read_only_fields = fields


class LedgerFlagsSerializer(serializers.Serializer):
    """What a staff payment row needs to show beyond the ledger columns."""

    method_label = serializers.CharField(allow_blank=True)
    awaiting_confirmation_id = serializers.IntegerField(allow_null=True)
    open_claim_id = serializers.IntegerField(allow_null=True)
    open_flags = serializers.IntegerField()
    disputed = serializers.BooleanField()
    taxed = serializers.BooleanField()
    pay_link_available = serializers.BooleanField(
        help_text="A pending account-less charge in a space with billing.pay_links on.")


def page_of(child, name):
    """The DRF page envelope every staff list returns, named for the OpenAPI component."""
    return type(name, (serializers.Serializer,), {
        "count": serializers.IntegerField(), "next": serializers.URLField(allow_null=True),
        "previous": serializers.URLField(allow_null=True), "results": child(many=True)})


ClaimPageSerializer = page_of(StaffClaimSerializer, "PaymentClaimPage")
ConfirmationPageSerializer = page_of(ConfirmationSerializer, "SettlementConfirmationPage")
CaptureFlagPageSerializer = page_of(CaptureFlagSerializer, "CaptureFlagPage")
DisputePageSerializer = page_of(DisputeSerializer, "PaymentDisputePage")
