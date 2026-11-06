"""Staff orders: list and detail (`VIEW_SHOP`), the desk's ready/collect/take-payment
(`SELL_SHOP`), cancelling, returns (`MANAGE_SHOP`, `shop.returns`) and receipts.

No route here moves money by itself: a return or a cancelled paid order opens a refund
case that staff approve in the refund queue (#59).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from .gates import MANAGE, SELL, VIEW, require_feature, staff_space
from .models import ShopOrder
from .serializers_public import ShopErrorSerializer
from .serializers_staff import (
    ShopCancelSerializer, ShopCollectSerializer, ShopDeskPaymentSerializer, ShopReceiptEmailSerializer, ShopReceiptSerializer,
    ShopReturnSerializer, ShopStaffOrderSerializer,
)
from .views_staff_catalogue import PAGE, page

TAGS = ["Admin shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 409)}
FILTERS = [*PAGE, OpenApiParameter("status", str, OpenApiParameter.QUERY),
           OpenApiParameter("channel", str, OpenApiParameter.QUERY),
           OpenApiParameter("code", str, OpenApiParameter.QUERY)]


def order_for(request, pk, action=VIEW):
    order = get_object_or_404(ShopOrder.objects.select_related("makerspace", "buyer", "pickup_event"), pk=pk)
    staff_space(request.user, order.makerspace_id, action)
    return order


def _out(request, order):
    order = ShopOrder.objects.select_related("buyer", "pickup_event").prefetch_related("lines", "returns").get(
        pk=order.pk)
    return Response(ShopStaffOrderSerializer(order, context={"request": request}).data)


class ShopOrderListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=FILTERS, responses={200: ShopStaffOrderSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, VIEW)
        rows = ShopOrder.objects.filter(makerspace=space).select_related("buyer", "pickup_event").prefetch_related(
            "lines", "returns")
        query = request.query_params
        if query.get("status") in ShopOrder.Status.values:
            rows = rows.filter(status=query["status"])
        if query.get("channel") in ShopOrder.Channel.values:
            rows = rows.filter(channel=query["channel"])
        if query.get("code"):
            rows = rows.filter(pickup_code=query["code"].strip().upper()[:12])
        return page(request, rows, ShopStaffOrderSerializer)


class ShopOrderDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, responses={200: ShopStaffOrderSerializer, **ERRORS})
    def get(self, request, pk):
        return _out(request, order_for(request, pk))


class ShopOrderReadyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=None, responses={200: ShopStaffOrderSerializer, **ERRORS},
                   summary="Put a paid order on the pickup shelf (the buyer is told)")
    def post(self, request, pk):
        from .services_orders import mark_ready
        return _out(request, mark_ready(order_for(request, pk, SELL), actor=request.user))


class ShopOrderCollectView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopCollectSerializer, responses={200: ShopStaffOrderSerializer, **ERRORS},
                   summary="Hand a paid order over against its pickup code")
    def post(self, request, pk):
        from .services_orders import collect
        body = ShopCollectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return _out(request, collect(order_for(request, pk, SELL), actor=request.user,
                                     code=body.validated_data["pickup_code"]))


class ShopOrderTakePaymentView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopDeskPaymentSerializer, responses={200: ShopStaffOrderSerializer, **ERRORS},
                   summary="Take payment at the desk for a pay-at-desk order (cash, UPI or card)")
    def post(self, request, pk):
        from .services_pos import collect_payment
        body = ShopDeskPaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return _out(request, collect_payment(order_for(request, pk, SELL), actor=request.user,
                                             **body.validated_data))


class ShopOrderCancelView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopCancelSerializer, responses={200: ShopStaffOrderSerializer, **ERRORS},
                   summary="Cancel an unpaid order, or (shop managers) a paid order never collected")
    def post(self, request, pk):
        from .services_orders import cancel_uncollected, cancel_unpaid
        body = ShopCancelSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        order = order_for(request, pk, SELL)
        if order.status in ShopOrder.OPEN_STATUSES:
            return _out(request, cancel_unpaid(order, actor=request.user, reason="staff"))
        order = order_for(request, pk, MANAGE)
        return _out(request, cancel_uncollected(order, actor=request.user, reason=body.validated_data["reason"]))


class ShopOrderReturnView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopReturnSerializer, responses={200: ShopStaffOrderSerializer, **ERRORS},
                   summary="Take items back (restock or write off) and open the refund case")
    def post(self, request, pk):
        from .services_returns import record_return
        order = order_for(request, pk, MANAGE)
        require_feature(order.makerspace, "shop.returns")
        body = ShopReturnSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        record_return(order, actor=request.user, rows=body.validated_data["rows"],
                      reason=body.validated_data["reason"])
        return _out(request, order)


class ShopOrderReceiptView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, responses={200: ShopReceiptSerializer, **ERRORS},
                   summary="The receipt or tax invoice, itemised for 80 mm and A4 printing")
    def get(self, request, pk):
        from .receipts import receipt_payload
        order = order_for(request, pk, VIEW)
        require_feature(order.makerspace, "shop.receipts")
        return Response(ShopReceiptSerializer(receipt_payload(order)).data)

    @extend_schema(tags=TAGS, request=ShopReceiptEmailSerializer, responses={204: None, **ERRORS},
                   summary="Email the receipt to the buyer")
    def post(self, request, pk):
        from .receipts import email_receipt
        order = order_for(request, pk, SELL)
        require_feature(order.makerspace, "shop.receipts")
        body = ShopReceiptEmailSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        email_receipt(order, body.validated_data.get("email", ""), actor=request.user)
        return Response(status=204)
