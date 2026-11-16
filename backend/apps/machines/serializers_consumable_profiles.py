"""Serializers for consumable profiles, their job usage and machine-type templates (decisions 341/343)."""

from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import InventoryProduct

from .consumable_profiles import EstimateBy, Kind, RECORDERS, Unit
from .models import MachineConsumablePool
from .models_consumable_profiles import MachineTypeConsumable, ServiceRequestConsumableUsage


class ConsumableEntrySerializer(serializers.Serializer):
    """One `{key, quantity, attributes}` entry: an estimate or an actual, by profile key."""

    key = serializers.RegexField(r"^[a-z][a-z0-9_]{0,49}$")
    quantity = serializers.DecimalField(max_digits=16, decimal_places=3, min_value=Decimal("0.001"))
    attributes = serializers.DictField(child=serializers.CharField(max_length=100), required=False, default=dict)


class ConsumableDefinitionSerializer(serializers.ModelSerializer):
    record_by = serializers.ListField(child=serializers.ChoiceField(choices=RECORDERS), min_length=1, max_length=3)
    attributes = serializers.DictField(child=serializers.ListField(child=serializers.CharField(max_length=100)),
                                       required=False)
    consumable_pool = serializers.PrimaryKeyRelatedField(queryset=MachineConsumablePool.objects.all(),
                                                         required=False, allow_null=True)
    product = serializers.PrimaryKeyRelatedField(queryset=InventoryProduct.objects.all(), required=False,
                                                 allow_null=True)
    consumable_pool_label = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    in_use = serializers.SerializerMethodField()

    class Meta:
        model = MachineTypeConsumable
        fields = ["id", "machine_type", "key", "name", "kind", "unit", "attributes", "required", "estimate_by",
                  "record_by", "unit_price", "consumable_pool", "consumable_pool_label", "product", "product_name",
                  "position", "is_active", "template_key", "in_use", "created_at", "updated_at"]
        read_only_fields = ["id", "machine_type", "template_key", "created_at", "updated_at"]

    def get_consumable_pool_label(self, row) -> str:
        return row.consumable_pool.label if row.consumable_pool_id else ""

    def get_product_name(self, row) -> str:
        return row.product.name if row.product_id else ""

    def get_in_use(self, row) -> bool:
        return row.usage.exists()


class ConsumableDefinitionUpdateSerializer(ConsumableDefinitionSerializer):
    class Meta(ConsumableDefinitionSerializer.Meta):
        read_only_fields = [*ConsumableDefinitionSerializer.Meta.read_only_fields, "key"]


class MemberJobConsumableSerializer(serializers.Serializer):
    """What a member's request form shows: no stock links, no prices it cannot act on."""

    key = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.ChoiceField(choices=Kind.choices)
    unit = serializers.ChoiceField(choices=Unit.choices)
    attributes = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))
    required = serializers.BooleanField()
    estimate_by = serializers.ChoiceField(choices=EstimateBy.choices)
    member_reports = serializers.SerializerMethodField()

    def get_member_reports(self, row) -> bool:
        return "member" in row.record_by


class MemberReportableConsumableSerializer(MemberJobConsumableSerializer):
    recorded_quantity = serializers.DecimalField(max_digits=16, decimal_places=3, allow_null=True)


class JobConsumableUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequestConsumableUsage
        fields = ["id", "key", "name", "kind", "unit", "phase", "quantity", "attributes", "source", "unit_price",
                  "created_at"]


class JobConsumablesSerializer(serializers.Serializer):
    profile = ConsumableDefinitionSerializer(many=True)
    estimates = JobConsumableUsageSerializer(many=True)
    actuals = JobConsumableUsageSerializer(many=True)
    missing_required = serializers.ListField(child=serializers.CharField())


class RecordConsumablesSerializer(serializers.Serializer):
    phase = serializers.ChoiceField(choices=["estimate", "actual"])
    entries = ConsumableEntrySerializer(many=True, max_length=32)


class MachineTypeTemplateSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, read_only=True)
    key = serializers.RegexField(r"^[a-z][a-z0-9_]{0,49}$")
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    category = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    icon = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    spec = serializers.JSONField()
    is_builtin = serializers.BooleanField(read_only=True)
    customised = serializers.BooleanField(read_only=True)
    based_on = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(required=False, default=True)


class ApplyMachineTypeTemplateSerializer(serializers.Serializer):
    machine_type_id = serializers.IntegerField(required=False, allow_null=True, min_value=1, default=None)
    name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    slug = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class ApplyMachineTypeTemplateResultSerializer(serializers.Serializer):
    machine_type_id = serializers.IntegerField()
    created_type = serializers.BooleanField()
    template_key = serializers.CharField()
    consumables_added = serializers.ListField(child=serializers.CharField())
    consumables_skipped = serializers.ListField(child=serializers.CharField())
    prefill = serializers.JSONField()
