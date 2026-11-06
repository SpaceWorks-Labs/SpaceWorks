"""Core wire types remain usable with both Events and the online rail removed."""
from django.utils.translation import gettext
from rest_framework import serializers
from datetime import datetime
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
            raise serializers.ValidationError(gettext("Unsupported currency.")) from None


class AwareDateTime(serializers.DateTimeField):
    def to_internal_value(self, data):
        try:
            value = datetime.fromisoformat(data.replace("Z", "+00:00")) if isinstance(data, str) else data
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError()
        except (ValueError, TypeError):
            raise serializers.ValidationError(gettext("An offset-aware datetime is required.")) from None
        return super().to_internal_value(data)


class Boolean(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid")
        return super().to_internal_value(data)


class Command(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = Integer(min_value=1)


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.DictField(required=False)


ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 413, 416, 423, 429, 503)}


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
    allowed_actions = serializers.ListField(child=serializers.CharField())


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
    hold_id = serializers.UUIDField(required=False)


class PayeeCommand(Command):
    expected_payee_version = Integer(min_value=1, allow_null=True)
    country = serializers.RegexField(r"^[A-Z]{2}$")
    template_key = serializers.CharField(max_length=24)
    template_version = Integer(min_value=1)
    method = serializers.ChoiceField(choices=sorted(METHODS))
    details = serializers.DictField()
    disclosure_version = Integer(min_value=1)


class RevealCommand(Command):
    expected_payee_version = Integer(min_value=1)
    purpose = serializers.ChoiceField(choices=("verify_routing",))
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{0,63}$")


class RevealSerializer(serializers.Serializer):
    payee_revision_id = serializers.UUIDField()
    details = serializers.DictField()


# Frozen G1 public serializer spellings; old imports remain compatible.
class OwnerPayeeCommand(PayeeCommand):
    pass


class OwnerPayeeDeleteCommand(Command):
    pass


class PayeeRevealCommand(RevealCommand):
    pass
