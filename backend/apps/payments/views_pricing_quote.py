"""`POST pricing/quote`: the price preview members and visitors see (lane L15, A6/A8).

Anonymous allowed, throttled per IP (`THROTTLE_PRICING_QUOTE`). A signed-in member of
the space gets their own price. Only publicly shown things can be quoted, and the answer
holds prices only -- never hidden counts, storage, box, QR or requester data.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.lookup import get_public_makerspace
from apps.payments.models_pricing import PricingDomain
from apps.payments.pricing.http import require_pricing
from apps.payments.pricing.public_quote import public_quote
from apps.payments.pricing.serializers import PricingQuoteSerializer


class PricingQuoteThrottle(UserRateThrottle):
    """Per account when signed in, per IP otherwise."""

    scope = "pricing_quote"


class PricingQuoteItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=1000)


class PricingQuoteRequestSerializer(serializers.Serializer):
    domain = serializers.ChoiceField(choices=PricingDomain.choices)
    items = PricingQuoteItemSerializer(many=True, required=False, max_length=50)
    days = serializers.IntegerField(min_value=0, max_value=365, required=False)
    request_id = serializers.IntegerField(min_value=1, required=False, help_text="The member's own loan request.")
    space_id = serializers.IntegerField(min_value=1, required=False)
    space_token = serializers.UUIDField(required=False, help_text="A room's public token, instead of space_id.")
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    machine_id = serializers.IntegerField(min_value=1, required=False)
    machine_type_id = serializers.IntegerField(min_value=1, required=False)
    pool_id = serializers.IntegerField(min_value=1, required=False)
    minutes = serializers.IntegerField(min_value=0, max_value=100000, required=False)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    event_id = serializers.IntegerField(min_value=1, required=False)
    event_token = serializers.UUIDField(required=False, help_text="An event's public token, instead of event_id.")
    ticket_type_id = serializers.IntegerField(min_value=1, required=False)
    plan_id = serializers.IntegerField(min_value=1, required=False)
    joining = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if attrs.get("starts_at") and attrs.get("ends_at") and attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({"ends_at": "The end must be after the start."})
        return attrs


class PricingQuoteTaxSerializer(serializers.Serializer):
    net = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax = serializers.DecimalField(max_digits=12, decimal_places=2)
    gross = serializers.DecimalField(max_digits=12, decimal_places=2)
    inclusive = serializers.BooleanField()
    mode = serializers.CharField()


class PricingQuoteDepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    refundable = serializers.BooleanField()


class PricingQuotePolicySerializer(serializers.Serializer):
    late_per_day = serializers.DecimalField(max_digits=12, decimal_places=2)
    late_cap = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    grace_days = serializers.IntegerField()
    damage_default = serializers.DecimalField(max_digits=12, decimal_places=2)
    lost_default = serializers.DecimalField(max_digits=12, decimal_places=2)
    damage_lost_text = serializers.CharField()


class PricingPublicQuoteSerializer(serializers.Serializer):
    quote = PricingQuoteSerializer()
    digest = serializers.CharField()
    tax = PricingQuoteTaxSerializer()
    members_total = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    member_price_applied = serializers.BooleanField()
    deposit = PricingQuoteDepositSerializer(allow_null=True)
    policy = PricingQuotePolicySerializer(allow_null=True)
    refund_summary = serializers.CharField(allow_null=True)


class PricingQuoteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PricingQuoteThrottle]

    @extend_schema(tags=["Pricing"], summary="Preview a price (anonymous allowed)",
                   description="Quotes a public item, room, machine (or type), event or plan. Signed-in members of "
                               "the space get their own price. Send `digest` back on submit: a moved price is "
                               "409 `price_changed` with the new quote. 404 when the thing is not public, the "
                               "module is off or `charges.pricing` is off, and 404 `charges_off` when that "
                               "domain's charges are not tracked (charges.enabled or charges.<domain> off): "
                               "the domain is free.",
                   request=PricingQuoteRequestSerializer,
                   responses={200: PricingPublicQuoteSerializer, 400: OpenApiResponse(ErrorSerializer),
                              404: OpenApiResponse(ErrorSerializer), 429: OpenApiResponse(ErrorSerializer)})
    def post(self, request, makerspace_slug):
        body = PricingQuoteRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        space = get_public_makerspace(makerspace_slug)
        require_pricing(space)
        viewer = request.user if getattr(request.user, "is_authenticated", False) else None
        return Response(PricingPublicQuoteSerializer(public_quote(space, data["domain"], viewer, data)).data)
