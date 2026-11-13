"""The public ticket shop of an event (release 2 L6, G29/G30/G34).

What a buyer needs before paying: ticket types on sale to them (tiers with a "next tier"
hint, pay-what-you-want minimums, group sizes, quantity rules), add-ons, the booking fee
and the refund policy text. Hidden ticket types never appear here -- an access code
reveals them in the order quote. Exact places left are shown only when the event shows
counts; otherwise just "sold out". No hidden counts, stock levels or buyer data.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import feature_enabled


class ShopTierSerializer(serializers.Serializer):
    name = serializers.CharField()
    amount = MoneyField(max_digits=13, decimal_places=3)


class ShopTicketSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    amount = MoneyField(max_digits=13, decimal_places=3)
    audience = serializers.CharField()
    pricing_mode = serializers.CharField()
    min_amount = MoneyField(max_digits=13, decimal_places=3)
    seats_per_ticket = serializers.IntegerField()
    min_quantity = serializers.IntegerField()
    per_order_limit = serializers.IntegerField()
    spots_left = serializers.IntegerField(allow_null=True)
    sold_out = serializers.BooleanField()
    next_tier = ShopTierSerializer(allow_null=True)


class ShopVariantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    sold_out = serializers.BooleanField()


class ShopAddonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    kind = serializers.CharField()
    amount = MoneyField(max_digits=13, decimal_places=3)
    per_order_limit = serializers.IntegerField()
    sold_out = serializers.BooleanField()
    variants = ShopVariantSerializer(many=True)


class AccessCodesSerializer(serializers.Serializer):
    access_codes = serializers.ListField(child=serializers.CharField(max_length=128), min_length=1, max_length=5)


class TicketShopSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    orders_enabled = serializers.BooleanField()
    currency = serializers.CharField()
    ticket_types = ShopTicketSerializer(many=True)
    addons = ShopAddonSerializer(many=True)
    booking_fee_fixed = MoneyField(max_digits=13, decimal_places=3)
    booking_fee_bps = serializers.IntegerField()
    max_tickets_per_order = serializers.IntegerField()
    promo_codes_enabled = serializers.BooleanField()
    policy = serializers.JSONField()


def _tickets(event, user, unlocked=()):
    from .capacity import registration_spots_left
    from .ticket_tiers import next_tier
    from .ticketing import available_ticket_types
    rows = []
    for ticket in available_ticket_types(event, user, unlocked=unlocked):
        left = registration_spots_left(event, ticket)
        tier = next_tier(event, ticket)
        rows.append({"id": ticket.pk, "name": ticket.name, "amount": ticket.amount, "audience": ticket.audience,
                     "pricing_mode": ticket.pricing_mode, "min_amount": ticket.min_amount,
                     "seats_per_ticket": ticket.seats_per_ticket, "min_quantity": ticket.min_quantity,
                     "per_order_limit": ticket.per_order_limit,
                     "spots_left": left if event.show_registration_count else None,
                     "sold_out": left is not None and left < ticket.seats_per_ticket,
                     "next_tier": {"name": tier.name, "amount": tier.amount} if tier else None})
    return rows


def _addons(event):
    from .addons import remaining
    if not feature_enabled(event.makerspace, "events.addons"):
        return []
    rows = []
    for addon in event.addons.filter(is_active=True).prefetch_related("variants").order_by("pk"):
        variants = [{"id": v.pk, "label": v.label, "sold_out": remaining(addon, v) == 0}
                    for v in addon.variants.all() if v.is_active]
        rows.append({"id": addon.pk, "name": addon.name, "description": addon.description, "kind": addon.kind,
                     "amount": addon.amount, "per_order_limit": addon.per_order_limit,
                     "sold_out": all(v["sold_out"] for v in variants) if variants else remaining(addon) == 0,
                     "variants": variants})
    return rows


class PublicEventTicketShopView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public events"], auth=[], request=None, responses={200: TicketShopSerializer})
    def get(self, request, makerspace_slug, public_token):
        return self.shop(request, makerspace_slug, public_token)

    @extend_schema(tags=["Public events"], auth=[], request=AccessCodesSerializer,
                   summary="The shop with the hidden tickets these access codes unlock (writes nothing)",
                   responses={200: TicketShopSerializer, 404: OpenApiResponse(description="access_code_invalid")})
    def post(self, request, makerspace_slug, public_token):
        body = AccessCodesSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self.shop(request, makerspace_slug, public_token, codes=body.validated_data["access_codes"])

    def shop(self, request, makerspace_slug, public_token, codes=()):
        from apps.payments.pricing.rates import RateCard
        from .orders_codes import unlocked_types
        from .cancellation_policy import policy_summary
        from .orders_quote import sales_settings
        from .views_public import _public_events
        space = get_public_makerspace(makerspace_slug)
        require_module_for_servable(space, "events")
        event = get_object_or_404(_public_events(space).select_related("makerspace"), public_token=public_token)
        user = request.user if request.user.is_authenticated else None
        settings_row = sales_settings(event)
        unlocked = unlocked_types(event, codes)[0] if codes else ()
        return Response(TicketShopSerializer({
            "event_id": event.pk, "orders_enabled": feature_enabled(space, "events.orders"),
            "currency": RateCard(space, "events").currency, "ticket_types": _tickets(event, user, unlocked),
            "addons": _addons(event), "booking_fee_fixed": settings_row.booking_fee_fixed,
            "booking_fee_bps": settings_row.booking_fee_bps,
            "max_tickets_per_order": settings_row.max_tickets_per_order,
            "promo_codes_enabled": feature_enabled(space, "events.promo_codes"),
            "policy": policy_summary(event)}).data)
