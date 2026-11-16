from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.operations.serializers_reports_base import (
    ReportRowsFieldMixin,
    TypedReportBaseSerializer,
)
from apps.payments.models import Payment


class PaymentReportFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Payment.Status.choices, required=False)
    subject_type = serializers.ChoiceField(
        choices=Payment.SubjectType.choices, required=False
    )


class PaymentReconciliationReportRowSerializer(TypedReportBaseSerializer):
    currency = serializers.CharField()
    subject_type = serializers.CharField()
    status = serializers.CharField()
    payment_count = serializers.IntegerField()
    amount_total = MoneyField(max_digits=21, decimal_places=3)
    outstanding_amount = MoneyField(max_digits=21, decimal_places=3)
    settlement_method = serializers.CharField(allow_blank=True)
    refunded_amount = MoneyField(max_digits=21, decimal_places=3)


class PaymentReconciliationReportSerializer(ReportRowsFieldMixin):
    typed_rows = PaymentReconciliationReportRowSerializer(many=True)


class PaymentCashBookRowSerializer(TypedReportBaseSerializer):
    currency = serializers.CharField()
    method = serializers.CharField()
    collected_amount = MoneyField(max_digits=21, decimal_places=3)
    refunded_amount = MoneyField(max_digits=21, decimal_places=3)
    net_amount = MoneyField(max_digits=21, decimal_places=3)


class PaymentCashBookSerializer(ReportRowsFieldMixin):
    typed_rows = PaymentCashBookRowSerializer(many=True)
