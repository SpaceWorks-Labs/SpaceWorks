"""Explicit OpenAPI shapes for each registered finance report."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from apps.operations.serializers_reports_base import ReportRowsFieldMixin, TypedReportBaseSerializer


class FinanceAmountsSerializer(TypedReportBaseSerializer):
    currency = serializers.CharField()
    collected_amount = MoneyField(max_digits=21, decimal_places=3)
    refunded_amount = MoneyField(max_digits=21, decimal_places=3)


class LedgerLineSerializer(FinanceAmountsSerializer):
    date = serializers.DateTimeField()
    row_kind = serializers.CharField()
    row_id = serializers.IntegerField()
    payment_id = serializers.IntegerField()
    document_number = serializers.CharField(allow_blank=True)
    subject_type = serializers.CharField()
    payer_type = serializers.CharField()
    payer_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    amount = MoneyField(max_digits=21, decimal_places=3)
    owed_amount = MoneyField(max_digits=21, decimal_places=3)
    method = serializers.CharField(allow_blank=True)
    reference = serializers.CharField(allow_blank=True)
    effective = serializers.BooleanField()
    refund_status = serializers.CharField(allow_blank=True)


class RevenuePeriodSerializer(FinanceAmountsSerializer):
    period = serializers.DateField()
    subject_type = serializers.CharField()
    rail = serializers.ChoiceField(choices=("online", "offline", "unallocated"))
    owed_amount = MoneyField(max_digits=21, decimal_places=3)
    waived_amount = MoneyField(max_digits=21, decimal_places=3)
    net_amount = MoneyField(max_digits=21, decimal_places=3)


class CashPeriodSerializer(FinanceAmountsSerializer):
    period = serializers.DateField()
    method = serializers.CharField()
    net_amount = MoneyField(max_digits=21, decimal_places=3)


class JournalLineSerializer(TypedReportBaseSerializer):
    date = serializers.DateField()
    document_number = serializers.CharField()
    kind = serializers.CharField()
    payment_id = serializers.IntegerField()
    subject_type = serializers.CharField()
    currency = serializers.CharField()
    account_code = serializers.CharField()
    debit = MoneyField(max_digits=21, decimal_places=3)
    credit = MoneyField(max_digits=21, decimal_places=3)
    settlement_method = serializers.CharField()


class PaymentsLedgerReportSerializer(ReportRowsFieldMixin):
    typed_rows = LedgerLineSerializer(many=True)


class RevenueOverTimeReportSerializer(ReportRowsFieldMixin):
    typed_rows = RevenuePeriodSerializer(many=True)


class CashBookReportSerializer(ReportRowsFieldMixin):
    typed_rows = CashPeriodSerializer(many=True)


class AccountingJournalReportSerializer(ReportRowsFieldMixin):
    typed_rows = JournalLineSerializer(many=True)


class PaymentAgeingRowSerializer(TypedReportBaseSerializer):
    currency = serializers.CharField()
    age_bucket = serializers.ChoiceField(choices=("0-30", "31-60", "61-90", "90+"))
    payment_count = serializers.IntegerField()
    outstanding_amount = MoneyField(max_digits=25, decimal_places=3)


class PaymentsAgeingReportSerializer(ReportRowsFieldMixin):
    typed_rows = PaymentAgeingRowSerializer(many=True)
