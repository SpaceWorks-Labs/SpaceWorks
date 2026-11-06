"""Staff shapes for ticketing v2 (release 2 L6): add-ons, passes, sales rules, refund override,
venue fees, orders and desk collection."""

from django.utils.translation import gettext
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.payments.models import ManualSettlement

from .models import EventAddon, EventAddonVariant, EventPassType, EventSalesSettings, EventVenueFee
from .serializers_ticketing_orders import OrderSerializer


class AddonVariantSerializer(serializers.ModelSerializer):
    remaining = serializers.SerializerMethodField()

    class Meta:
        model = EventAddonVariant
        fields = ("id", "label", "stock", "is_active", "remaining")
        read_only_fields = ("id", "remaining")

    def get_remaining(self, obj) -> int | None:
        from .addons import remaining
        return remaining(obj.addon, obj)


class AddonSerializer(serializers.ModelSerializer):
    variants = AddonVariantSerializer(many=True, required=False)
    remaining = serializers.SerializerMethodField()
    sold = serializers.SerializerMethodField()

    class Meta:
        model = EventAddon
        fields = ("id", "name", "description", "kind", "amount", "stock", "per_order_limit", "is_active",
                  "variants", "remaining", "sold")
        read_only_fields = ("id", "remaining", "sold")

    def get_remaining(self, obj) -> int | None:
        from .addons import remaining
        return remaining(obj)

    def get_sold(self, obj) -> int:
        from .addons import sold
        return sold(obj)


class PassTypeStaffSerializer(serializers.ModelSerializer):
    sold = serializers.SerializerMethodField()

    class Meta:
        model = EventPassType
        fields = ("id", "name", "amount", "capacity", "occurrence_refund_amount", "sales_end_at", "is_active", "sold")
        read_only_fields = ("id", "sold")

    def get_sold(self, obj) -> int:
        from .passes import passes_sold
        return passes_sold(obj)


class SalesSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSalesSettings
        fields = ("booking_fee_fixed", "booking_fee_bps", "max_tickets_per_order", "transfers_allowed",
                  "type_changes_allowed", "transfer_cutoff_hours")


class EventRefundPolicyInputSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    full_before_minutes = serializers.IntegerField(min_value=0, max_value=525600)
    partial_before_minutes = serializers.IntegerField(min_value=0, max_value=525600)
    partial_percent = serializers.IntegerField(min_value=0, max_value=100)
    cancellation_fee = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    policy_text = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class EventRefundPolicySerializer(serializers.Serializer):
    overridden = serializers.BooleanField()
    locked = serializers.BooleanField(help_text="True after the first sale: changes may only be more generous.")
    terms = serializers.JSONField(allow_null=True)
    text = serializers.CharField(allow_blank=True)


class VenueFeeInputSerializer(serializers.Serializer):
    payer_id = serializers.IntegerField(min_value=1)
    organization_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    room_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=EventVenueFee.Mode.choices)
    basis = serializers.ChoiceField(choices=EventVenueFee.Basis.choices, default="flat")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)


class VenueFeeSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    payer_name = serializers.SerializerMethodField()
    quote_total = serializers.SerializerMethodField()
    payment_id = serializers.SerializerMethodField()
    pii_account_fields = ("payer_name",)

    class Meta:
        model = EventVenueFee
        fields = ("id", "payer", "payer_name", "organization", "room", "mode", "basis", "amount", "status",
                  "charged_at", "quote_total", "payment_id")
        read_only_fields = fields

    def get_payer_name(self, obj) -> str:
        return obj.payer.display_name or obj.payer.get_full_name() or obj.payer.username

    def get_quote_total(self, obj) -> str:
        from .venue_fees import venue_quote
        return str(venue_quote(obj.event, obj).total)

    def get_payment_id(self, obj) -> int | None:
        from apps.payments.models import Payment
        return Payment.objects.filter(makerspace_id=obj.makerspace_id, subject_type="event_venue_fee",
                                      subject_id=obj.pk).values_list("pk", flat=True).first()


class DeskCollectSerializer(serializers.Serializer):
    terminal = serializers.BooleanField(default=False, help_text="True: open a pay-now checkout instead of a receipt.")
    method = serializers.ChoiceField(choices=ManualSettlement.Method.choices, required=False)
    reference = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    received_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if not attrs.get("terminal") and not attrs.get("method"):
            raise serializers.ValidationError({"method": gettext("Choose how the money was received.")})
        return attrs


class DeskCollectResultSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    payment_status = serializers.CharField()
    checkout_url = serializers.CharField(allow_blank=True)


class StaffOrderSerializer(OrderSerializer):
    buyer_name = serializers.SerializerMethodField()
    pii_account_fields = ("buyer_name",)

    class Meta(OrderSerializer.Meta):
        fields = (*OrderSerializer.Meta.fields, "buyer", "buyer_name")
        read_only_fields = fields

    def get_buyer_name(self, obj) -> str:
        return obj.buyer.display_name or obj.buyer.get_full_name() or obj.buyer.username


class StaffOrderListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = StaffOrderSerializer(many=True)


class AddonListSerializer(StaffOrderListSerializer):
    results = AddonSerializer(many=True)


class PassTypeListSerializer(StaffOrderListSerializer):
    results = PassTypeStaffSerializer(many=True)
