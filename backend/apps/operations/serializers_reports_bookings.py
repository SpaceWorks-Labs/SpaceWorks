from rest_framework import serializers

from .serializers_reports_base import ReportRowsFieldMixin
from .serializers_reports_fablab import BookingUtilizationRowSerializer


class BookingReportMetaSerializer(serializers.Serializer):
    source = serializers.CharField()
    grain = serializers.CharField()
    rollup_through = serializers.CharField(allow_null=True)
    arrival_counts_available = serializers.BooleanField(required=False)


class BookingReportResponseSerializer(ReportRowsFieldMixin):
    report_key = serializers.CharField()
    meta = BookingReportMetaSerializer()


class BookingResourceUtilizationRowSerializer(BookingUtilizationRowSerializer):
    arrived_reservations = serializers.IntegerField(help_text="Reservations with a current, unreversed arrival.")
    confirmed_without_recorded_arrival = serializers.IntegerField(
        help_text="Confirmed reservations with no current arrival; not a no-show count.")


class BookingResourceUtilizationReportSerializer(BookingReportResponseSerializer):
    typed_rows = BookingResourceUtilizationRowSerializer(many=True)


class BookingReservationReportRowSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    space_id = serializers.IntegerField()
    space_name = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    organization = serializers.CharField(allow_blank=True, allow_null=True)  # decision 223 (k): report v2 column


class BookingAnswerReportRowSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    space_id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()
    answers = serializers.CharField(help_text="JSON of the stored custom-answer snapshot; null when absent.")


class BookingReservationReportSerializer(BookingReportResponseSerializer):
    typed_rows = BookingReservationReportRowSerializer(many=True)


class BookingAnswerReportSerializer(BookingReportResponseSerializer):
    typed_rows = BookingAnswerReportRowSerializer(many=True)
