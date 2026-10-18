"""Finance commands are explicit, reauthenticated recording instructions."""
from rest_framework import serializers
from .serializers import Command, Integer, Currency
from .validation import MAX_MINOR, METHODS


class CancelUnpaidObligationCommand(Command):
    expected_revision_sequence = Integer(min_value=1)
    expected_pool_version = Integer(min_value=1, allow_null=True)
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")
    note = serializers.CharField(max_length=5000)


class RecordPayoutCommand(Command):
    amount_minor = Integer(min_value=1, max_value=MAX_MINOR)
    currency = Currency()
    method = serializers.ChoiceField(choices=sorted(METHODS))
    reference = serializers.CharField(max_length=64, trim_whitespace=True)
    paid_at = serializers.DateTimeField()
    payee_revision = serializers.UUIDField()
    expected_payee_version = Integer(min_value=1)
    eligibility_revision = Integer(min_value=1)
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$", required=False)


class AmendPayoutCommand(RecordPayoutCommand):
    amount_minor = Integer(min_value=0, max_value=MAX_MINOR)
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")
    is_void = serializers.BooleanField(default=False)
    payee_revision = serializers.UUIDField(allow_null=True)


class PayeeVerifyCommand(Command):
    payee_revision_id = serializers.UUIDField()
    expected_payee_version = Integer(min_value=1)
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$", required=False)


class PayeeCorrectionCommand(PayeeVerifyCommand):
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")
    note = serializers.CharField(max_length=5000)


class PayoutHoldCommand(Command):
    eligibility_revision = Integer(min_value=1)
    kind = serializers.ChoiceField(choices=("eligibility", "retention"))
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")
    note = serializers.CharField(max_length=5000, default="", allow_blank=True)
    evidence_refs = serializers.ListField(child=Integer(min_value=1), default=list, max_length=100)
    hold_until = serializers.DateTimeField(required=False, allow_null=True)


class ReleasePayoutHoldCommand(PayoutHoldCommand):
    hold_id = serializers.UUIDField()


class EligibilityAcknowledgementCommand(Command):
    eligibility_revision = Integer(min_value=1)
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")


class PayoutExportCommand(Command):
    expected_version = Integer(min_value=0, max_value=0)
    obligation_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=500)
