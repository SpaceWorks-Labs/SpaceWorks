"""Request and response shapes of the collection sheet and the cash hand-over (parity O-B3)."""

from datetime import timedelta
from decimal import Decimal
from django.utils.translation import gettext
from django.utils import timezone
from rest_framework import serializers

from apps.payments.collection_sheet import MAX_ROWS
from apps.payments.models import ManualSettlement
from apps.payments.money_fields import MoneyField


class CollectionRowSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(choices=ManualSettlement.Method.choices)
    reference = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    received_at = serializers.DateTimeField(required=False)

    def validate_received_at(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError(gettext("A settlement cannot be received in the future."))
        return value


class CollectionSheetSerializer(serializers.Serializer):
    rows = CollectionRowSerializer(many=True, allow_empty=False, max_length=MAX_ROWS)


class CollectionResultSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    payment_id = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=["recorded", "awaiting_confirmation", "failed"])
    code = serializers.CharField(allow_blank=True)
    detail = serializers.CharField(allow_blank=True)


class CollectionSummarySerializer(serializers.Serializer):
    rows = serializers.IntegerField()
    recorded = serializers.IntegerField()
    awaiting_confirmation = serializers.IntegerField()
    failed = serializers.IntegerField()


class CollectionSheetResponseSerializer(serializers.Serializer):
    summary = CollectionSummarySerializer()
    results = CollectionResultSerializer(many=True)


class CashHandoverSerializer(serializers.Serializer):
    collector_id = serializers.IntegerField(min_value=1)
    amount = MoneyField(max_digits=13, decimal_places=3, min_value=Decimal("0.001"))
    currency = serializers.RegexField(r"^[A-Za-z]{3}$")
    entry_date = serializers.DateField(required=False)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class CashHandoverResultSerializer(serializers.Serializer):
    entry_id = serializers.IntegerField()
    collector_id = serializers.IntegerField()
    amount = MoneyField(max_digits=13, decimal_places=3)
    currency = serializers.CharField()
