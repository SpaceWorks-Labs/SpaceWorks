from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.events.models import EventCategory, EventInvite, EventPromoCode, EventTicketType


class InviteInputSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True, write_only=True)
    max_uses = serializers.IntegerField(min_value=1, default=1, required=False)
    expires_at = serializers.DateTimeField(allow_null=True, required=False)


class InviteSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, help_text="Returned once on creation only.")

    class Meta:
        model = EventInvite
        fields = ("id", "max_uses", "uses", "expires_at", "revoked_at", "created_at", "code")
        read_only_fields = fields


class PromoInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=128, min_length=8, required=False, write_only=True)
    # Release 2 L6 (G29): access codes unlock one hidden ticket type; discounts per ticket or order.
    kind = serializers.ChoiceField(choices=("discount", "access"), default="discount", required=False)
    applies_per = serializers.ChoiceField(choices=("ticket", "order"), default="ticket", required=False)
    ticket_type_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    percent_off = serializers.IntegerField(min_value=0, max_value=100, default=0, required=False)
    amount_off = MoneyField(max_digits=13, decimal_places=3, min_value=0, default=0, required=False)
    max_uses = serializers.IntegerField(min_value=1, default=1, required=False)
    expires_at = serializers.DateTimeField(allow_null=True, required=False)


class PromoSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, help_text="Returned once on creation only.")

    class Meta:
        model = EventPromoCode
        fields = ("id", "percent_off", "amount_off", "max_uses", "uses", "expires_at", "revoked_at", "created_at", "code",
                  "kind", "applies_per", "ticket_type")
        read_only_fields = fields


class TicketInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventTicketType
        fields = ("name", "amount", "audience", "capacity", "sales_start_at", "sales_end_at",
                  "purpose", "contributor_capacity_policy",
                  # Release 2 L6 (G29): tiers, pay-what-you-want, group seats, hidden tickets, order limits.
                  "tier_group", "tier_rank", "pricing_mode", "min_amount", "seats_per_ticket", "is_hidden", "min_quantity", "per_order_limit")


class TicketSerializer(TicketInputSerializer):
    registration_count = serializers.SerializerMethodField()

    class Meta(TicketInputSerializer.Meta):
        fields = ("id", *TicketInputSerializer.Meta.fields, "is_active", "registration_count")
        read_only_fields = fields

    def get_registration_count(self, obj) -> int:
        from apps.events.models import EventRegistration
        return EventRegistration.objects.filter(ticket_type=obj).count()


class CategoryInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ("name", "slug")


class CategorySerializer(CategoryInputSerializer):
    event_count = serializers.SerializerMethodField()

    class Meta(CategoryInputSerializer.Meta):
        fields = ("id", "name", "slug", "event_count")
        read_only_fields = fields

    def get_event_count(self, obj) -> int:
        return obj.events.count()


class InviteListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = InviteSerializer(many=True)


class PromoListSerializer(InviteListSerializer):
    results = PromoSerializer(many=True)


class TicketListSerializer(InviteListSerializer):
    results = TicketSerializer(many=True)


class CategoryListSerializer(InviteListSerializer):
    results = CategorySerializer(many=True)
