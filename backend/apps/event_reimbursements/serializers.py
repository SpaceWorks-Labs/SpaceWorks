"""Strict member commands and stable ID-only mutation receipts."""
from rest_framework import serializers as s
from drf_spectacular.utils import extend_schema_serializer
from .serializers_request import ClosedSerializer, StrictInteger, ReimbursementRequestSubmissionSerializer
from .claim_inputs import ClaimLineInput


class Command(ClosedSerializer):
    operation_id = s.UUIDField()
    expected_version = StrictInteger(min_value=0)


class RequestSubmitCommand(Command):
    reimbursement_request = ReimbursementRequestSubmissionSerializer()


class AwardResponseCommand(Command):
    award_revision = StrictInteger(min_value=1)


class ClaimDraftCommand(Command):
    lines = ClaimLineInput(many=True, allow_empty=True, max_length=50)


class ClaimSubmitCommand(Command):
    current_revision = StrictInteger(min_value=1, allow_null=True)


class ClaimAppealCommand(ClaimSubmitCommand):
    statement = s.CharField(max_length=5000, allow_blank=False)


@extend_schema_serializer(component_name="ReimbursementCommandResult")
class CommandResult(s.Serializer):
    id = s.IntegerField()
    version = s.IntegerField()
    state = s.CharField()
    uuid = s.UUIDField(required=False)
    pool_id = s.IntegerField(required=False)
    pool_version = s.IntegerField(required=False)
    created = s.BooleanField(required=False)
    award_id = s.IntegerField(required=False, allow_null=True)
    award_version = s.IntegerField(required=False, allow_null=True)
    claim_revision_id = s.IntegerField(required=False)
    appeal_id = s.IntegerField(required=False)
    review_id = s.IntegerField(required=False)
    decision_id = s.IntegerField(required=False)
    decision_sequence = s.IntegerField(required=False)
    obligation_id = s.UUIDField(required=False, allow_null=True)
    due_revision = s.IntegerField(required=False)
    attestation_id = s.IntegerField(required=False)
    attestation_uuid = s.UUIDField(required=False)
    attendance_revision = s.IntegerField(required=False)
    override_id = s.UUIDField(required=False)
    receipt_use_version = s.IntegerField(required=False)
    ledger_entry_id = s.IntegerField(required=False, allow_null=True, help_text="Hack-money G12: the booking's expense.")


class ReceiptUploadCommand(Command):
    claim_uuid = s.UUIDField()
    question_id = s.ChoiceField(choices=("receipt",))
    filename = s.CharField(max_length=255)
    bytes = StrictInteger(min_value=1, max_value=10485760)
    mime = s.ChoiceField(choices=("application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif"))


class ReceiptCompleteCommand(Command):
    generation = StrictInteger(min_value=1)


class ReceiptMetadata(s.Serializer):
    asset_id = s.IntegerField()
    filename = s.CharField()
    generation = s.IntegerField()
    version = s.IntegerField()
    state = s.CharField()
    sha256 = s.CharField()
    bytes = s.IntegerField(allow_null=True)
    mime = s.CharField()
    scan_status = s.CharField()
    expires_at = s.DateTimeField(allow_null=True)


@extend_schema_serializer(component_name="ReimbursementUpload")
class Upload(s.Serializer):
    method = s.CharField()
    url = s.URLField()
    fields = s.DictField(child=s.CharField())
    expires_at = s.DateTimeField()


class ReceiptUploadResult(s.Serializer):
    asset_id = s.IntegerField()
    generation = s.IntegerField()
    state = s.CharField()
    upload = Upload()


class ReceiptCompleteResult(s.Serializer):
    asset_id = s.IntegerField()
    generation = s.IntegerField()
    state = s.CharField()
    status_url = s.CharField()
