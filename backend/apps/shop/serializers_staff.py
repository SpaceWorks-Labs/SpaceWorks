"""Staff shop shapes (release 2 L22): catalogue, stock, orders, desk, cash-up and settings.

Buyer names and emails on an order are scoped PII: a superadmin without an open PII window
sees them masked (`PiiMaskingSerializerMixin`, #114.1).
"""

from django.utils.translation import gettext
from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin

from .models import ShopCashSession, ShopOrder, ShopProduct, ShopSettings, ShopStockMovement, ShopVariant
from .serializers_public import ShopLineInputSerializer, ShopOrderLineSerializer

from .pickup_status import pickup_event_title, pickup_requires_staff_confirmation

from apps.payments.money import MONEY  # noqa: E402


class ShopStaffVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    linked_product_id = serializers.IntegerField(required=False, allow_null=True)
    available = serializers.SerializerMethodField()

    class Meta:
        model = ShopVariant
        fields = ("id", "name", "options", "sku", "price", "on_hand", "held", "reorder_point", "linked_product_id",
                  "is_active", "sort_order", "archived_at", "available")
        read_only_fields = ("on_hand", "held", "archived_at", "available")

    def get_available(self, variant) -> int:
        from apps.inventory.availability import shop_sellable
        return shop_sellable(variant)


class ShopComponentSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)


class ShopProductSerializer(serializers.ModelSerializer):
    variants = ShopStaffVariantSerializer(many=True, required=False)
    components = serializers.SerializerMethodField()
    component_input = ShopComponentSerializer(many=True, required=False, write_only=True, source="components_in")
    image_url = serializers.SerializerMethodField()
    price = MoneyField(**MONEY, required=False, write_only=True, min_value=0)

    class Meta:
        model = ShopProduct
        fields = ("id", "kind", "name", "slug", "description", "image_url", "category", "is_public", "is_active",
                  "sort_order", "unit", "max_per_order", "members_only", "show_exact_stock", "tax_rate_bps",
                  "hsn_code", "bundle_mode", "archived_at", "created_at", "updated_at", "variants", "components",
                  "component_input", "price")
        read_only_fields = ("archived_at", "created_at", "updated_at")
        extra_kwargs = {"slug": {"required": False}}

    def get_components(self, product) -> list[dict]:
        return [{"variant_id": part.component_id, "quantity": part.quantity} for part in product.components.all()]

    def get_image_url(self, product) -> str:
        from apps.inventory import public_image_storage
        return public_image_storage.public_url(product.image_key) or ""


class ShopStockMoveSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("restock", "count", "damage", "internal_use"))
    quantity = serializers.IntegerField(min_value=-100000, max_value=100000)
    reason = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")

    def validate(self, attrs):
        if attrs["kind"] == "restock" and attrs["quantity"] <= 0:
            raise serializers.ValidationError({"quantity": gettext("A restock adds at least one unit.")})
        if attrs["kind"] != "restock" and not attrs.get("reason", "").strip():
            raise serializers.ValidationError({"reason": gettext("Say why the count changed.")})
        if attrs["quantity"] == 0:
            raise serializers.ValidationError({"quantity": gettext("Enter a change other than zero.")})
        return attrs


class ShopMovementSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ShopStockMovement
        fields = ("id", "variant", "kind", "quantity", "balance_after", "reason", "order", "actor_name", "created_at")

    def get_actor_name(self, row) -> str:
        return getattr(row.actor, "username", "") if row.actor_id else ""


class ShopReturnRowSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999)
    disposition = serializers.ChoiceField(choices=("restock", "write_off"))


class ShopReturnSerializer(serializers.Serializer):
    rows = ShopReturnRowSerializer(many=True, min_length=1, max_length=50)
    reason = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")


class ShopStaffReturnSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    line_id = serializers.IntegerField()
    quantity = serializers.IntegerField()
    disposition = serializers.CharField()
    amount = MoneyField(**MONEY)
    refund_case_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class ShopStaffOrderSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    lines = ShopOrderLineSerializer(many=True, read_only=True)
    returns = ShopStaffReturnSerializer(many=True, read_only=True)
    buyer_name = serializers.SerializerMethodField()
    buyer_email = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    pickup_event_title = serializers.SerializerMethodField()
    pickup_requires_staff_confirmation = serializers.SerializerMethodField()
    pii_account_fields = ("buyer_name", "buyer_email")

    class Meta:
        model = ShopOrder
        fields = ("id", "makerspace", "channel", "status", "buyer", "buyer_name", "buyer_email", "guest_name",
                  "guest_email", "pickup_at", "pickup_event", "pickup_event_title", "pickup_code", "currency",
                  "pickup_requires_staff_confirmation",
                  "subtotal", "discount_total", "total", "tax_total", "amount_due", "created_at", "expires_at",
                  "paid_at", "ready_at", "collected_at", "closed_at", "close_reason", "cash_session", "lines",
                  "returns", "payment_status")

    def get_buyer_name(self, order) -> str:
        if order.buyer_id:
            return (order.buyer.get_full_name() or getattr(order.buyer, "display_name", "") or order.buyer.username)
        return order.guest_name

    def get_buyer_email(self, order) -> str:
        return (order.buyer.email or "") if order.buyer_id else order.guest_email

    def get_payment_status(self, order) -> str:
        from .orders_core import order_payment
        payment = order_payment(order)
        return payment.status if payment else "none"

    def get_pickup_event_title(self, order) -> str:
        return pickup_event_title(order)

    def get_pickup_requires_staff_confirmation(self, order) -> bool:
        return pickup_requires_staff_confirmation(order)


class ShopDeskPaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=("cash", "upi", "card_machine"), default="cash")
    reference = serializers.CharField(max_length=64, allow_blank=True, required=False, default="")
    received_at = serializers.DateTimeField(required=False, allow_null=True)
    hand_over = serializers.BooleanField(required=False, default=True)


class ShopPosQuoteSerializer(serializers.Serializer):
    lines = ShopLineInputSerializer(many=True, min_length=1, max_length=50)
    member_id = serializers.IntegerField(required=False, allow_null=True)


class ShopPosSaleSerializer(ShopPosQuoteSerializer, ShopDeskPaymentSerializer):
    quote_digest = serializers.CharField(required=False, allow_blank=True, max_length=64)
    receipt_email = serializers.EmailField(required=False, allow_blank=True, max_length=254)


class ShopCollectSerializer(serializers.Serializer):
    pickup_code = serializers.CharField(max_length=12)


class ShopCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")


class ShopMemberHitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ShopCashOpenSerializer(serializers.Serializer):
    opening_float = MoneyField(**MONEY, min_value=0)


class ShopCashCloseSerializer(serializers.Serializer):
    counted_cash = MoneyField(**MONEY, min_value=0)
    note = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")


class ShopCashSessionSerializer(serializers.ModelSerializer):
    expected_now = serializers.SerializerMethodField()

    class Meta:
        model = ShopCashSession
        fields = ("id", "status", "currency", "opening_float", "opened_by", "opened_at", "counted_cash",
                  "expected_cash", "variance", "note", "closed_by", "closing_at", "confirmed_by", "closed_at",
                  "expected_now")

    def get_expected_now(self, session) -> str | None:
        from .services_cash import expected_cash
        return str(expected_cash(session)[0]) if session.status == ShopCashSession.Status.OPEN else None


class ShopSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopSettings
        fields = ("online_hold_minutes", "desk_hold_hours", "returns_window_days", "first_reminder_days",
                  "second_reminder_days", "uncollected_cancel_days", "policy_text", "pickup_note", "updated_at")
        read_only_fields = ("updated_at",)


class ShopReceiptLineSerializer(serializers.Serializer):
    label = serializers.CharField()
    sku = serializers.CharField(allow_blank=True)
    quantity = serializers.IntegerField()
    unit_amount = MoneyField(**MONEY)
    discount_amount = MoneyField(**MONEY)
    line_total = MoneyField(**MONEY)
    hsn_code = serializers.CharField(allow_blank=True)
    tax_rate_bps = serializers.IntegerField(allow_null=True)
    tax_amount = MoneyField(**MONEY, allow_null=True)


class ShopReceiptSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    space_name = serializers.CharField()
    supplier_gstin = serializers.CharField(allow_blank=True)
    document_number = serializers.CharField(allow_blank=True)
    document_title = serializers.CharField(allow_blank=True)
    issued_at = serializers.DateTimeField(allow_null=True)
    buyer_name = serializers.CharField(allow_blank=True)
    pickup_code = serializers.CharField()
    channel = serializers.CharField()
    currency = serializers.CharField()
    lines = ShopReceiptLineSerializer(many=True)
    subtotal = MoneyField(**MONEY)
    discount_total = MoneyField(**MONEY)
    tax_total = MoneyField(**MONEY)
    total = MoneyField(**MONEY)
    status = serializers.CharField()
    paid = serializers.BooleanField()
    method = serializers.CharField(allow_blank=True)
    notes = serializers.ListField(child=serializers.CharField())


class ShopReceiptEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
