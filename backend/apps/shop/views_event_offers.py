"""Shop merch at events (#135 Q-S18 follow-up): the staff offer list and the public event list.

Staff routes resolve the space through rbac (`VIEW_SHOP` reads, `MANAGE_SHOP` writes), so
another space's id answers 404. The public route reads an event by its public token and
answers 404 when the online shop, `shop.event_pickup` or Events is off.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import ClientTierRateThrottle

from .gates import MANAGE, VIEW, public_space, staff_space
from .serializers_public import ShopErrorSerializer, ShopPickupEventSerializer, ShopPublicProductSerializer


class ShopEventOfferRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    status = serializers.CharField()
    variant_ids = serializers.ListField(child=serializers.IntegerField())


class ShopEventOfferSetSerializer(serializers.Serializer):
    variant_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=50, allow_empty=True)


class ShopEventOfferSavedSerializer(serializers.Serializer):
    variant_ids = serializers.ListField(child=serializers.IntegerField())


class ShopPublicEventOffersSerializer(serializers.Serializer):
    event = ShopPickupEventSerializer()
    currency = serializers.CharField()
    products = ShopPublicProductSerializer(many=True)


STAFF_TAGS, PUBLIC_TAGS = ["Admin shop"], ["Public shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 409)}


class ShopEventOfferListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, responses={200: ShopEventOfferRowSerializer(many=True), **ERRORS},
                   summary="Upcoming events and the shop items each one offers")
    def get(self, request, makerspace_id):
        from .event_offers import staff_rows
        space = staff_space(request.user, makerspace_id, VIEW)
        return Response(ShopEventOfferRowSerializer(staff_rows(space, request.user), many=True).data)


class ShopEventOfferDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, request=ShopEventOfferSetSerializer,
                   responses={200: ShopEventOfferSavedSerializer, **ERRORS},
                   summary="Replace the shop items one event offers (bought as ordinary shop orders)")
    def put(self, request, makerspace_id, event_id):
        from .event_offers import set_offers
        space = staff_space(request.user, makerspace_id, MANAGE)
        body = ShopEventOfferSetSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        ids = set_offers(space, event_id, body.validated_data["variant_ids"], actor=request.user)
        return Response(ShopEventOfferSavedSerializer({"variant_ids": ids}).data)


class PublicShopEventOffersView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=PUBLIC_TAGS, auth=[], responses={200: ShopPublicEventOffersSerializer,
                                                         **{**ERRORS, 429: ShopErrorSerializer}},
                   summary="The shop items an event offers, for pickup at that event")
    def get(self, request, makerspace_slug, public_token):
        from .event_offers import public_offers
        payload = public_offers(public_space(makerspace_slug), public_token)
        return Response(ShopPublicEventOffersSerializer(payload).data)
