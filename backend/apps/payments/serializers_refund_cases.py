"""Refund case and refund policy shapes for staff, and the member's narrow view."""

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.payments.models import RefundCase
from apps.payments.serializers_reconciliation import RefundSerializer
from apps.payments.serializers_refunds_offline import ManualRefundReceiptSerializer
from apps.payments.subjects import subject_label


class RefundCasePaymentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subject_type = serializers.CharField()
    subject_label = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    member_name = serializers.CharField(allow_blank=True)


class RefundCaseSerializer(serializers.ModelSerializer):
    payment = serializers.SerializerMethodField()
    refund = RefundSerializer(read_only=True, allow_null=True)
    refundable_balance = serializers.SerializerMethodField()
    #: Lane L24: a price-difference case is decided by the Space Manager or a finance admin.
    needs_finance_approval = serializers.SerializerMethodField()

    class Meta:
        model = RefundCase
        fields = ("id", "payment", "kind", "area", "reason_code", "member_reason", "due_amount",
                  "policy_snapshot", "status", "approved_amount", "decision_note", "refund",
                  "refundable_balance", "needs_finance_approval", "created_at", "decided_at")
        read_only_fields = fields

    @extend_schema_field(RefundCasePaymentSerializer)
    def get_payment(self, case):
        payment, member = case.payment, case.payment.member
        name = (member.display_name or member.get_full_name() or member.username) if member else ""
        return RefundCasePaymentSerializer({
            "id": payment.pk, "subject_type": payment.subject_type,
            "subject_label": subject_label(payment, self.context.get("payment_subject_labels", {})),
            "status": payment.status, "amount": payment.amount, "currency": payment.currency,
            "member_name": name,
        }).data

    @extend_schema_field(serializers.BooleanField())
    def get_needs_finance_approval(self, case) -> bool:
        from apps.payments.price_drop.approval import needs_finance_approval
        return needs_finance_approval(case)

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_refundable_balance(self, case):
        # Read from the prefetched refund lines (`refund_case_access.with_case_rows`), so
        # a page of cases costs no query per row. Same rule as `Refund.counted_total`.
        from apps.payments.models import Refund
        counted = sum((row.amount for row in case.payment.refunds.all()
                       if row.status in Refund.COUNTED_STATUSES and not hasattr(row, "amended_by")),
                      Decimal("0.00"))
        return str(max(case.payment.amount - counted, Decimal("0.00")))


class RefundCaseListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RefundCaseSerializer(many=True)


class RefundCaseFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RefundCase.Status.choices, required=False)
    area = serializers.ChoiceField(choices=RefundCase.Area.choices, required=False)
    kind = serializers.ChoiceField(choices=RefundCase.Kind.choices, required=False)


class RefundCaseApproveSerializer(serializers.Serializer):
    # Omitted: the case's due amount, re-clamped to the live refundable balance.
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    # Required for a charge settled offline: the money goes back in person.
    receipt = ManualRefundReceiptSerializer(required=False)
    # X21 (L4): approving a membership refund ends the term it paid for unless staff tick this.
    keep_membership = serializers.BooleanField(required=False, default=False)


class RefundCaseDeclineSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500)


class MemberRefundCaseSerializer(serializers.ModelSerializer):
    """The payer sees where their refund stands and why -- nothing staff-internal."""

    withdrawable = serializers.SerializerMethodField()

    class Meta:
        model = RefundCase
        fields = ("id", "kind", "status", "decision_note", "withdrawable", "created_at", "decided_at")
        read_only_fields = fields

    def get_withdrawable(self, case) -> bool:
        return case.kind == RefundCase.Kind.REQUEST and case.status == RefundCase.Status.OPEN


class MemberRefundRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
