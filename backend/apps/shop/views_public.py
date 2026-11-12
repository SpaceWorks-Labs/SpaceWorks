"""The public shop (`shop.online`): browse, quote, the guest email code, order and status.

Anonymous reads; ordering needs a signed-in person, or a guest with a confirmed email when
`shop.guest_checkout` is on (Q-S5). With the module or `shop.online` off every route is 404.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle

from .gates import public_space
from .serializers_public import (
    ShopBuyerOrderSerializer, ShopEmailCodeSerializer, ShopOrderCreateSerializer, ShopOrderPlacedSerializer, ShopPublicProductSerializer,
    ShopQuoteRequestSerializer, ShopErrorSerializer, ShopQuoteSerializer, ShopSummarySerializer,
)

TAGS = ["Public shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 409, 429)}
PAGE = [OpenApiParameter("page", int, OpenApiParameter.QUERY), OpenApiParameter("category", str, OpenApiParameter.QUERY)]


class _Public(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"


class PublicShopView(_Public):
    @extend_schema(tags=TAGS, auth=[], responses={200: ShopSummarySerializer, **ERRORS})
    def get(self, request, makerspace_slug):
        from .public import shop_summary
        return Response(ShopSummarySerializer(shop_summary(public_space(makerspace_slug))).data)


class PublicProductListView(_Public):
    @extend_schema(tags=TAGS, auth=[], parameters=PAGE, responses={200: ShopPublicProductSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_slug):
        from .public import product_payload, public_products
        space = public_space(makerspace_slug)
        rows = public_products(space)
        if request.query_params.get("category"):
            rows = rows.filter(category=request.query_params["category"][:80])
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response([product_payload(space, row) for row in page])


class PublicProductDetailView(_Public):
    @extend_schema(tags=TAGS, auth=[], responses={200: ShopPublicProductSerializer, **ERRORS})
    def get(self, request, makerspace_slug, product_slug):
        from .public import product_payload, public_products
        space = public_space(makerspace_slug)
        product = get_object_or_404(public_products(space), slug=product_slug)
        return Response(product_payload(space, product, detail=True))


class PublicShopQuoteView(_Public):
    throttle_scope = "pricing_quote"

    @extend_schema(tags=TAGS, auth=[], request=ShopQuoteRequestSerializer, responses={200: ShopQuoteSerializer, **ERRORS},
                   summary="Price a basket (the same quote the order is charged at)")
    def post(self, request, makerspace_slug):
        from .pricing import priced_basket, quote_payload
        space = public_space(makerspace_slug)
        body = ShopQuoteRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        basket = priced_basket(space, body.validated_data["lines"], person=request.user, public=True)
        return Response(ShopQuoteSerializer(quote_payload(space, basket)).data)


class PublicShopEmailCodeView(_Public):
    throttle_scope = "shop_codes"

    @extend_schema(tags=TAGS, auth=[], request=ShopEmailCodeSerializer, responses={204: None, **ERRORS},
                   summary="Email a one-time code so a guest can order (#80 machinery)")
    def post(self, request, makerspace_slug):
        from .checkout import send_code
        space = public_space(makerspace_slug)
        body = ShopEmailCodeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        send_code(space, body.validated_data["email"])
        return Response(status=204)


class PublicShopOrderView(_Public):
    throttle_scope = "shop_orders"

    # Optional auth: a member bearer token attaches the order to that account; without one
    # it is a guest order (needs `shop.guest_checkout` and a confirmed email code).
    @extend_schema(tags=TAGS, auth=[{"jwtAuth": []}, {}], request=ShopOrderCreateSerializer, responses={201: ShopOrderPlacedSerializer, **ERRORS},
                   parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=False,
                               description="Optional client key (up to 64 characters). A repeat with the same key returns the first order instead of placing a second.")],
                   summary="Place an order: hold the stock, then pay online or at the desk")
    def post(self, request, makerspace_slug):
        from .checkout import buyer_for, checkout_url, place_online_order
        from .notices import status_token
        space = public_space(makerspace_slug)
        body = ShopOrderCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        buyer = buyer_for(request, space, data)
        order, payment = place_online_order(space, buyer, data,
                                            idempotency_key=request.headers.get("Idempotency-Key", ""))
        order.refresh_from_db()
        return Response(ShopOrderPlacedSerializer({
            "order": order, "checkout_url": checkout_url(payment),
            "status_token": status_token(order) if buyer.is_guest else ""}).data, status=201)


class PublicShopOrderStatusView(_Public):
    @extend_schema(tags=TAGS, auth=[], responses={200: ShopBuyerOrderSerializer, **ERRORS},
                   summary="A guest's order, by the signed link in their email")
    def get(self, request, makerspace_slug, token):
        from .errors import ShopRefused
        from .notices import order_for_token
        space = public_space(makerspace_slug)
        order = order_for_token(token, makerspace=space)
        if order is None:
            raise ShopRefused("not_found", gettext("Order not found."))
        return Response(ShopBuyerOrderSerializer(order).data)
