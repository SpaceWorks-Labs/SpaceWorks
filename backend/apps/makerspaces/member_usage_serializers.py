"""Typed personal summaries and the common chart-spec contract."""

from rest_framework import serializers

from apps.operations.serializers_report_chart import ReportChartSpecSerializer


class MemberUsageSeriesSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.DictField(child=serializers.JSONField()))
    chart_spec = ReportChartSpecSerializer()


class MemberLoanUsageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    returned_count = serializers.IntegerField()
    currently_out = serializers.IntegerField()
    monthly = MemberUsageSeriesSerializer()


class MemberMachineUsageSerializer(serializers.Serializer):
    hours = serializers.CharField()
    monthly = MemberUsageSeriesSerializer()
    top_machines = MemberUsageSeriesSerializer()


class MemberBookingUsageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    monthly = MemberUsageSeriesSerializer()


class MemberEventUsageSerializer(serializers.Serializer):
    attended_count = serializers.IntegerField()
    chart = MemberUsageSeriesSerializer()


class MemberPaymentUsageSerializer(serializers.Serializer):
    paid_by_currency = serializers.DictField(child=serializers.CharField())
    outstanding_by_currency = serializers.DictField(child=serializers.CharField())
    totals = MemberUsageSeriesSerializer()


class MemberUsageSerializer(serializers.Serializer):
    usage_available = serializers.BooleanField(help_text="Active membership and membership module enabled.")
    loans = MemberLoanUsageSerializer(required=False)
    machines = MemberMachineUsageSerializer(required=False)
    bookings = MemberBookingUsageSerializer(required=False)
    events = MemberEventUsageSerializer(required=False)
    payments = MemberPaymentUsageSerializer(required=False)
