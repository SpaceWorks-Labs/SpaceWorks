"""Order, seat and claim shapes for buyers and attendees (release 2 L6)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.payments.pricing.serializers import PricingQuoteSerializer

from .models import EventOrder, EventOrderLine, EventOrderSeat


class OrderTicketItemSerializer(serializers.Serializer):
    ticket_type_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False,
                                      help_text="Pay-what-you-want tickets only: the amount chosen.")


class OrderAddonItemSerializer(serializers.Serializer):
    addon_id = serializers.IntegerField(min_value=1)
    variant_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class OrderRequestSerializer(serializers.Serializer):
    tickets = OrderTicketItemSerializer(many=True, required=False, default=list,
                                        help_text="Empty only for an add-on-only order by a confirmed "
                                                  "registration on an approval event (events.accepted_addons).")
    addons = OrderAddonItemSerializer(many=True, required=False, default=list)
    promo_code = serializers.CharField(max_length=128, required=False, allow_blank=True, write_only=True)
    access_codes = serializers.ListField(child=serializers.CharField(max_length=128), required=False,
                                         default=list, max_length=5, write_only=True)
    buyer_attends = serializers.BooleanField(default=True)
    attendees = serializers.ListField(child=serializers.EmailField(), required=False, default=list, max_length=50,
                                      help_text="Emails for the other seats, in order. More can be added later.")
    digest = serializers.CharField(max_length=64, required=False, allow_blank=True,
                                   help_text="The quote digest shown; a moved price answers 409 price_changed.")


class OrderQuoteResponseSerializer(serializers.Serializer):
    quote = PricingQuoteSerializer()
    promo_saving = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    seats = serializers.IntegerField()
    policy = serializers.JSONField()


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventOrderLine
        fields = ("id", "kind", "label", "quantity", "seats_per_unit", "unit_amount", "discount_amount",
                  "line_total", "ticket_type", "addon", "variant", "pass_type")
        read_only_fields = fields


class OrderSeatSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    event_id = serializers.IntegerField(read_only=True)
    registration_id = serializers.IntegerField(read_only=True, allow_null=True)
    ticket_type_id = serializers.IntegerField(source="line.ticket_type_id", read_only=True, allow_null=True)

    class Meta:
        model = EventOrderSeat
        fields = ("id", "event_id", "ticket_type_id", "status", "attendee_email", "registration_id", "invited_at",
                  "reminded_at", "claimed_at")
        read_only_fields = fields


class OrderSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    seats = OrderSeatSerializer(many=True, read_only=True)
    event_title = serializers.SerializerMethodField()
    checkout_url = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_disputed = serializers.SerializerMethodField()
    hold_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = EventOrder
        fields = ("id", "kind", "status", "event", "series", "event_title", "currency", "subtotal", "discount_total",
                  "fee_total", "total", "created_at", "paid_at", "closed_at", "lines", "seats", "checkout_url",
                  "payment_status", "payment_disputed", "hold_expires_at")
        read_only_fields = fields

    def _payment(self, obj):
        cache = self.context.setdefault("order_payments", {})
        if obj.pk not in cache:
            from .orders_settlement import order_payment
            cache[obj.pk] = order_payment(obj)
        return cache[obj.pk]

    def get_event_title(self, obj) -> str:
        return obj.series.title if obj.series_id else obj.event.title

    def get_checkout_url(self, obj) -> str:
        from apps.payments.checkout_expiry import live_checkout_url
        payment = self._payment(obj)
        return live_checkout_url(payment) if payment is not None and obj.status == "pending" else ""

    def get_payment_status(self, obj) -> str | None:
        payment = self._payment(obj)
        return payment.status if payment is not None else None

    def get_payment_disputed(self, obj) -> bool:
        from apps.payments.services_disputes import is_disputed
        payment = self._payment(obj)
        return bool(payment is not None and is_disputed(payment))

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_hold_expires_at(self, obj):
        from .models import EventCheckoutHold
        hold = EventCheckoutHold.objects.filter(order=obj, released_at__isnull=True).first()
        return hold.expires_at if hold is not None else None


class OrderPlacedSerializer(serializers.Serializer):
    order = OrderSerializer()
    checkout_url = serializers.CharField(allow_blank=True)


class AttendeeAssignmentSerializer(serializers.Serializer):
    assignments = serializers.DictField(child=serializers.EmailField(allow_blank=True),
                                        help_text="Seat id -> attendee email (blank clears it).")


class TicketClaimInputSerializer(serializers.Serializer):
    custom_answers = serializers.JSONField(required=False)
    form_payload = serializers.JSONField(required=False)
    host_waiver_id = serializers.IntegerField(required=False)
    host_waiver_version = serializers.CharField(required=False, max_length=64)
    host_waiver_accepted = serializers.BooleanField(required=False)


class ClaimPreviewSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    makerspace_id = serializers.IntegerField()
    event_title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ticket_type = serializers.CharField(allow_blank=True)
    from_name = serializers.CharField()
    email_matches = serializers.BooleanField()


class ClaimResultSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    status = serializers.CharField()


class OrderListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = OrderSerializer(many=True)
