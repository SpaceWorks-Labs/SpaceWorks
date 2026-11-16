"""Typed OpenAPI rows for the extended communications and service reports."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from .report_fields_hi import COMMUNICATION_COUNTS
from .serializers_report_catalog import GenericAnalyticsReportSerializer


# The numeric allowlist is shared with the builder and organization combiner so
# adding a measured count cannot silently leave the API schema behind.
CommunicationCountsSerializer = type("CommunicationCountsSerializer", (serializers.Serializer,), {
    "__module__": __name__, **{field: serializers.IntegerField(min_value=0) for field in COMMUNICATION_COUNTS},
})


class CommunicationsHealthRowSerializer(CommunicationCountsSerializer):
    makerspace_id = serializers.IntegerField(required=False)
    period = serializers.DateField(allow_null=True, help_text="Null for the current consent snapshot.")
    module_key = serializers.CharField()
    channel = serializers.CharField()
    feature = serializers.CharField()
    provider_source = serializers.CharField()
    platform = serializers.CharField()
    audience = serializers.CharField()
    skip_reason = serializers.CharField()
    segment_source = serializers.ChoiceField(choices=["billed", "estimated", "not_applicable"])
    measurement = serializers.ChoiceField(choices=["delivery_cohort", "webhook_receipts", "current_consent_snapshot"])
    success_rate_percent = serializers.FloatField(allow_null=True)
    read_rate_percent = serializers.FloatField(allow_null=True)
    delivery_rate = serializers.FloatField(allow_null=True, help_text="Delivered / accepted; null for a zero denominator.")
    read_rate = serializers.FloatField(allow_null=True, help_text="Read / delivered; null for a zero denominator.")
    consented_member_count = serializers.IntegerField(allow_null=True, help_text="Current live consent among active local members; excluded from organization totals.")
    last_activity_at = serializers.DateTimeField(allow_null=True)


class CommunicationsHealthReportSerializer(GenericAnalyticsReportSerializer):
    typed_rows = CommunicationsHealthRowSerializer(many=True)


class PlatformServicesRowSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField(allow_null=True)
    period = serializers.DateField(allow_null=True)
    day = serializers.DateField()
    service = serializers.CharField()
    provider_source = serializers.CharField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    bucket = serializers.CharField()
    count = serializers.IntegerField(min_value=0)
    currency = serializers.CharField(allow_null=True)
    amount = MoneyField(max_digits=25, decimal_places=3, allow_null=True)
    purpose = serializers.ChoiceField(choices=["otp", "notifications"], allow_null=True,
                                    help_text="SMS OTP vs addressed notifications. Null for other services.")


class PlatformServicesReportSerializer(GenericAnalyticsReportSerializer):
    typed_rows = PlatformServicesRowSerializer(many=True)
