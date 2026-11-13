from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.machines.models import MakerspaceMachineTypePricing


class MachineTypePricingSerializer(serializers.ModelSerializer):
    machine_type_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = MakerspaceMachineTypePricing
        fields = ("machine_type_id", "rate_per_unit", "flat_fee", "payment_enabled")
        read_only_fields = fields


class MachineTypePricingSetSerializer(serializers.Serializer):
    rate_per_unit = MoneyField(max_digits=13, decimal_places=3, min_value=0)
    flat_fee = MoneyField(max_digits=13, decimal_places=3, min_value=0)
    payment_enabled = serializers.BooleanField()


class MachineTypePricingListSerializer(serializers.Serializer):
    currency = serializers.CharField(read_only=True)
    results = MachineTypePricingSerializer(many=True, read_only=True)
