"""Core wire types remain usable with both Events and the online rail removed."""
from rest_framework import serializers
from apps.payments.currencies import normalize_supported_currency
from .validation import MAX_MINOR, METHODS


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"code": "invalid_fields"})
        return super().to_internal_value(data)


class Integer(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class Currency(serializers.CharField):
    def to_internal_value(self, data):
        try:
            return normalize_supported_currency(data)
        except ValueError:
            raise serializers.ValidationError("Unsupported currency.") from None


class Command(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = Integer(min_value=1)


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.DictField(required=False)


ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 416, 423, 429, 503)}


class PayoutSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    version = Integer()
    event_id = Integer()
    event_title = serializers.CharField()
    currency = Currency()
    approved_minor = Integer()
    effective_paid_minor = Integer()
    remaining_minor = Integer()
    state = serializers.ChoiceField(choices=("open", "settled", "cancelled"))
    eligibility_status = serializers.ChoiceField(choices=("eligible", "held", "needs_acknowledgement"))
    eligibility_revision = Integer()
    current_revision_sequence = Integer(allow_null=True)
    coordination_state = serializers.ChoiceField(choices=("attached", "detached"))


class PayoutResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    version = Integer()
    state = serializers.CharField()
    entry_id = serializers.UUIDField(required=False)
    payee_revision_id = serializers.UUIDField(required=False)
    payee_version = Integer(required=False)
    cancellation_revision_id = Integer(required=False)
    sequence = Integer(required=False)
    terminal_financial_at = serializers.DateTimeField(required=False, allow_null=True)


class PayeeCommand(Command):
    expected_payee_version = Integer(min_value=1, allow_null=True)
    country = serializers.RegexField(r"^[A-Z]{2}$")
    template_key = serializers.CharField(max_length=24)
    template_version = Integer(min_value=1)
    method = serializers.ChoiceField(choices=sorted(METHODS))
    details = serializers.DictField()
    disclosure_version = Integer(min_value=1)


class RevealCommand(Command):
    purpose = serializers.ChoiceField(choices=("verify_routing",))
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")


class RevealSerializer(serializers.Serializer):
    payee_revision_id = serializers.UUIDField()
    details = serializers.DictField()
