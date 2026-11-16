from rest_framework import serializers
from .serializers_reports_base import ReportRowsFieldMixin


class EventRegistrationReportRowSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    answers = serializers.CharField()


class EventFeedbackReportRowSerializer(serializers.Serializer):
    response_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    registration_id = serializers.IntegerField(allow_null=True)
    answers = serializers.CharField()


class EventRegistrationReportSerializer(ReportRowsFieldMixin):
    typed_rows = EventRegistrationReportRowSerializer(many=True)


class EventFeedbackReportSerializer(ReportRowsFieldMixin):
    typed_rows = EventFeedbackReportRowSerializer(many=True)
