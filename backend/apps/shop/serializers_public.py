"""Public and member shop shapes (release 2 L22). No storage, cost, linked item or buyer data."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from drf_spectacular.utils import extend_schema_field

from .pickup_status import pickup_event_title, pickup_requires_staff_confirmation

from apps.payments.money import MONEY  # noqa: E402


class ShopErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()


class ShopPublicVariantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    options = serializers.DictField(child=serializers.CharField())
    price = MoneyField(**MONEY, allow_null=True, coerce_to_string=False)
    sold_out = serializers.BooleanField()
    stock_label = serializers.ChoiceField(choices=("in_stock", "low", "sold_out"), allow_null=True)
    stock_count = serializers.IntegerField(allow_null=True)


class ShopPublicProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.CharField()
    category = serializers.CharField(allow_blank=True)
    unit = serializers.CharField(allow_blank=True)
    image_url = serializers.CharField(allow_blank=True)
    price_from = MoneyField(**MONEY, allow_null=True, coerce_to_string=False)
    price_to = MoneyField(**MONEY, allow_null=True, coerce_to_string=False)
    members_only = serializers.BooleanField()
    max_per_order = serializers.IntegerField(allow_null=True)
    sold_out = serializers.BooleanField()
    variants = ShopPublicVariantSerializer(many=True)
    description = serializers.CharField(allow_blank=True, required=False)


class ShopPickupEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()


class ShopSummarySerializer(serializers.Serializer):
    name = serializers.CharField()
    currency = serializers.CharField()
    pay_online = serializers.BooleanField()
    guest_checkout = serializers.BooleanField()
    member_prices = serializers.BooleanField()
    policy_text = serializers.CharField(allow_blank=True)
    pickup_note = serializers.CharField(allow_blank=True)
    returns_days = serializers.IntegerField()
    hold_minutes = serializers.IntegerField(allow_null=True)
    pickup_events = ShopPickupEventSerializer(many=True)


class ShopLineInputSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class ShopQuoteRequestSerializer(serializers.Serializer):
    lines = ShopLineInputSerializer(many=True, min_length=1, max_length=50)


class ShopQuoteLineSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    label = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit_amount = MoneyField(**MONEY)
    discount = MoneyField(**MONEY)
    net = MoneyField(**MONEY)
    tax_rate_bps = serializers.IntegerField(allow_null=True)
    tax = MoneyField(**MONEY, allow_null=True)


class ShopQuoteSerializer(serializers.Serializer):
    currency = serializers.CharField()
    lines = ShopQuoteLineSerializer(many=True)
    subtotal = MoneyField(**MONEY)
    discount_total = MoneyField(**MONEY)
    total = MoneyField(**MONEY)
    tax_total = MoneyField(**MONEY)
    amount_due = MoneyField(**MONEY)
    tax_inclusive = serializers.BooleanField()
    discount_name = serializers.CharField(allow_blank=True)
    digest = serializers.CharField()


class ShopOrderCreateSerializer(ShopQuoteRequestSerializer):
    quote_digest = serializers.CharField(required=False, allow_blank=True, max_length=64)
    pickup_at = serializers.ChoiceField(choices=("space", "event"), required=False, default="space")
    pickup_event_id = serializers.IntegerField(required=False, allow_null=True)
    guest_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    guest_email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
    email_code = serializers.CharField(required=False, allow_blank=True, max_length=12)


class ShopEmailCodeSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class ShopOrderLineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    variant_id = serializers.IntegerField()
    label = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_amount = MoneyField(**MONEY)
    discount_amount = MoneyField(**MONEY)
    line_total = MoneyField(**MONEY)
    hsn_code = serializers.CharField(allow_blank=True)
    tax_rate_bps = serializers.IntegerField(allow_null=True)
    tax_amount = MoneyField(**MONEY)


class ShopBuyerReturnSerializer(serializers.Serializer):
    """Goods taken back, not a claim that money has been refunded."""

    line_id = serializers.IntegerField()
    quantity = serializers.IntegerField()
    amount = MoneyField(**MONEY)
    created_at = serializers.DateTimeField()


class ShopBuyerOrderSerializer(serializers.Serializer):
    """An order as its own buyer sees it (member area, guest status link)."""

    id = serializers.IntegerField()
    status = serializers.CharField()
    channel = serializers.CharField()
    pickup_code = serializers.CharField()
    pickup_at = serializers.CharField()
    pickup_event_title = serializers.SerializerMethodField()
    pickup_requires_staff_confirmation = serializers.SerializerMethodField()
    currency = serializers.CharField()
    subtotal = MoneyField(**MONEY)
    discount_total = MoneyField(**MONEY)
    total = MoneyField(**MONEY)
    tax_total = MoneyField(**MONEY)
    amount_due = MoneyField(**MONEY)
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    paid_at = serializers.DateTimeField(allow_null=True)
    ready_at = serializers.DateTimeField(allow_null=True)
    collected_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    returns = serializers.SerializerMethodField()
    lines = ShopOrderLineSerializer(many=True)
    space_name = serializers.CharField(source="makerspace.name")

    def get_pickup_event_title(self, order) -> str:
        return pickup_event_title(order)

    def get_pickup_requires_staff_confirmation(self, order) -> bool:
        return pickup_requires_staff_confirmation(order)

    @extend_schema_field(ShopBuyerReturnSerializer(many=True))
    def get_returns(self, order):
        from .buyer_history import returns_for_buyer

        return ShopBuyerReturnSerializer(returns_for_buyer(order), many=True).data


class ShopOrderPlacedSerializer(serializers.Serializer):
    order = ShopBuyerOrderSerializer()
    checkout_url = serializers.CharField(allow_blank=True)
    status_token = serializers.CharField(allow_blank=True)
