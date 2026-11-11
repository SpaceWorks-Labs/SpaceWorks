from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.operations.serializers_reports_base import ReportRowsFieldMixin, TypedReportBaseSerializer


class MemberRetentionRowSerializer(TypedReportBaseSerializer):
    cohort_month = serializers.CharField()
    months_after_join = serializers.IntegerField()
    cohort_members = serializers.IntegerField()
    eligible_members = serializers.IntegerField()
    retained_members = serializers.IntegerField()
    retention_percent = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)
    churned_members = serializers.IntegerField()
    reactivated_members = serializers.IntegerField()


class MemberRetentionReportSerializer(ReportRowsFieldMixin):
    typed_rows = MemberRetentionRowSerializer(many=True)
    meta = serializers.DictField()
    report_key = serializers.CharField()


class MembershipRevenueRowSerializer(TypedReportBaseSerializer):
    period = serializers.DateField()
    currency = serializers.CharField()
    plan_id = serializers.IntegerField()
    plan_name = serializers.CharField()
    recurring_members = serializers.IntegerField()
    mrr = MoneyField(max_digits=25, decimal_places=3)
    arr = MoneyField(max_digits=25, decimal_places=3)
    arpu = MoneyField(max_digits=25, decimal_places=3)
    churned_members = serializers.IntegerField()
    reactivated_members = serializers.IntegerField()


class MembershipRevenueReportSerializer(ReportRowsFieldMixin):
    typed_rows = MembershipRevenueRowSerializer(many=True)
    meta = serializers.DictField()
    report_key = serializers.CharField()


class MembershipGrowthRowSerializer(TypedReportBaseSerializer):
    period = serializers.DateField()
    new_members = serializers.IntegerField()
    activated_members = serializers.IntegerField()
    revoked_members = serializers.IntegerField()
    active_members = serializers.IntegerField()


class MembershipGrowthReportSerializer(ReportRowsFieldMixin):
    typed_rows = MembershipGrowthRowSerializer(many=True)
