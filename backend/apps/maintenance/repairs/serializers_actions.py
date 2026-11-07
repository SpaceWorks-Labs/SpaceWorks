"""Request bodies for the repairs routes (validated at the boundary, typed in OpenAPI)."""

from django.utils.translation import gettext
from rest_framework import serializers

from apps.payments.models_ledger_entries import LedgerEntry

from .models_issues import PRIORITY_CHOICES, SUBJECT_CHOICES

PHOTOS = serializers.ListField(child=serializers.CharField(max_length=2000), required=False, max_length=6,
                               default=list)


class IssuePhotoUploadSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=["image/jpeg", "image/png", "image/webp"])


class IssuePhotoUploadResponseSerializer(serializers.Serializer):
    photo_token = serializers.CharField()
    upload = serializers.DictField()
    max_bytes = serializers.IntegerField()


class IssueReportCreateSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField(min_value=1, required=False)
    makerspace_slug = serializers.SlugField(required=False)
    loan_id = serializers.IntegerField(min_value=1, required=False)
    booking_id = serializers.IntegerField(min_value=1, required=False)
    booking_token = serializers.UUIDField(required=False)
    machine_job_id = serializers.IntegerField(min_value=1, required=False)
    product_id = serializers.IntegerField(min_value=1, required=False)
    asset_id = serializers.IntegerField(min_value=1, required=False)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=4000)
    photos = PHOTOS

    def validate(self, attrs):
        sources = [name for name in ("loan_id", "booking_id", "booking_token", "machine_job_id") if attrs.get(name)]
        if len(sources) != 1:
            raise serializers.ValidationError({"source": gettext("Report from one loan, booking or machine job.")})
        return attrs


class PublicIssueReportCreateSerializer(IssueReportCreateSerializer):
    contact_name = serializers.CharField(max_length=200)
    contact_email = serializers.EmailField(max_length=254)
    email_code = serializers.CharField(max_length=12)
    machine_job_id = None

    def validate(self, attrs):
        if len([name for name in ("loan_id", "booking_id", "booking_token") if attrs.get(name)]) != 1:
            raise serializers.ValidationError({"source": gettext("Report from one loan or booking.")})
        return attrs


class IssueOpenSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(choices=SUBJECT_CHOICES)
    subject_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000, default="")
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, default="normal")


class IssueTriageSerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class IssueReportRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class IssueNoteSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class IssueAssignSerializer(serializers.Serializer):
    contact_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    myself = serializers.BooleanField(default=False)


class IssueUnassignSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField(min_value=1)


class IssueDispatchRequestSerializer(serializers.Serializer):
    contact_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=10)
    channels = serializers.ListField(child=serializers.ChoiceField(choices=["email", "telegram", "whatsapp", "sms"]),
                                     required=False, allow_null=True, default=None)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class RepairWorkLogSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["visit", "remark"])
    note = serializers.CharField(required=False, allow_blank=True, max_length=4000, default="")
    occurred_on = serializers.DateField(required=False, allow_null=True, default=None)
    contact_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    photos = PHOTOS


class RepairPartWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["used", "needed"])
    product_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    quantity = serializers.IntegerField(min_value=1, max_value=100000)


class RepairQuoteSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    currency = serializers.CharField(min_length=3, max_length=3)
    contact_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class RepairQuoteDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class RepairPayoutSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=3, default="")
    method = serializers.ChoiceField(choices=[LedgerEntry.Method.CASH, LedgerEntry.Method.UPI,
                                              LedgerEntry.Method.BANK_TRANSFER, LedgerEntry.Method.CHEQUE,
                                              LedgerEntry.Method.OTHER])
    reference = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")
    receipt_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    entry_date = serializers.DateField(required=False, allow_null=True, default=None)


class RepairFixSerializer(serializers.Serializer):
    resolution = serializers.CharField(max_length=4000)
    photos = PHOTOS


class ServiceStateChangeSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(choices=SUBJECT_CHOICES)
    subject_id = serializers.IntegerField(min_value=1)
    in_service = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")
    expected_back_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(required=False, allow_null=True, min_value=1, default=None)
    mode = serializers.ChoiceField(choices=["block", "warn"], default="block")
    issue_id = serializers.IntegerField(required=False, allow_null=True, min_value=1, default=None)
