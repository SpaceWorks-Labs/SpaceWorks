"""OpenAPI row contracts for booking/event analytics (no new routes)."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from .serializers_reports_base import ReportRowsFieldMixin, TypedReportBaseSerializer
from .serializers_reports_fablab import BookingUtilizationRowSerializer


class BookingUtilizationV2RowSerializer(BookingUtilizationRowSerializer):
    period = serializers.DateTimeField(required=False)
    reservations = serializers.IntegerField(required=False)
    terminal_reservations = serializers.IntegerField(required=False)
    cancellation_rate_percent = serializers.FloatField(allow_null=True, required=False)


class PeriodRowSerializer(TypedReportBaseSerializer):
    period = serializers.DateTimeField()


class BookingOccupancyRowSerializer(PeriodRowSerializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    hour = serializers.IntegerField(min_value=0, max_value=23)
    occupied_hours = serializers.DecimalField(max_digits=24, decimal_places=2)
    window_hours = serializers.DecimalField(max_digits=24, decimal_places=2)
    occupancy_percent = serializers.FloatField(allow_null=True)


class BookingLeadTimeRowSerializer(PeriodRowSerializer):
    lead_time_bucket = serializers.CharField()
    booking_count = serializers.IntegerField()


class BookingTopMemberRowSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(allow_null=True)
    member = serializers.CharField()
    booking_count = serializers.IntegerField()
    reserved_hours = serializers.DecimalField(max_digits=24, decimal_places=2)


class EventPeriodRowSerializer(PeriodRowSerializer):
    event_id = serializers.IntegerField()
    title = serializers.CharField()


class EventSignupsRowSerializer(EventPeriodRowSerializer):
    registrations = serializers.IntegerField()
    cumulative_registrations = serializers.IntegerField()


class EventRevenueRowSerializer(EventPeriodRowSerializer):
    currency = serializers.CharField()
    charge_count = serializers.IntegerField()
    charged_amount = MoneyField(max_digits=25, decimal_places=3)
    promo_discount_amount = MoneyField(max_digits=25, decimal_places=3)
    collected_amount = MoneyField(max_digits=25, decimal_places=3)
    refunded_amount = MoneyField(max_digits=25, decimal_places=3)
    outstanding_amount = MoneyField(max_digits=25, decimal_places=3)
    net_amount = MoneyField(max_digits=25, decimal_places=3)


class EventFunnelRowSerializer(EventPeriodRowSerializer):
    registrations = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    attended = serializers.IntegerField()
    confirmation_rate_percent = serializers.FloatField(allow_null=True)
    attendance_rate_percent = serializers.FloatField(allow_null=True)


class EventCheckinTimesRowSerializer(EventPeriodRowSerializer):
    timing_bucket = serializers.CharField()
    checkin_count = serializers.IntegerField()


class EventFeedbackScoresRowSerializer(EventPeriodRowSerializer):
    question_id = serializers.CharField()
    score_count = serializers.IntegerField()
    score_total = serializers.DecimalField(max_digits=24, decimal_places=2)
    average_score = serializers.DecimalField(max_digits=24, decimal_places=2)


def _report(name, row):
    return type(name, (ReportRowsFieldMixin,), {"typed_rows": row(many=True)})


BookingUtilizationV2ReportSerializer = _report("BookingUtilizationV2ReportSerializer", BookingUtilizationV2RowSerializer)
DE_REPORT_SERIALIZERS = (
    _report("BookingOccupancyReportSerializer", BookingOccupancyRowSerializer),
    _report("BookingLeadTimeReportSerializer", BookingLeadTimeRowSerializer),
    _report("BookingTopMembersReportSerializer", BookingTopMemberRowSerializer),
    _report("EventSignupsReportSerializer", EventSignupsRowSerializer),
    _report("EventRevenueReportSerializer", EventRevenueRowSerializer),
    _report("EventFunnelReportSerializer", EventFunnelRowSerializer),
    _report("EventCheckinTimesReportSerializer", EventCheckinTimesRowSerializer),
    _report("EventFeedbackScoresReportSerializer", EventFeedbackScoresRowSerializer),
)
