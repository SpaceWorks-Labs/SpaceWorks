"""A signed-in buyer's own shop orders (member area): list, detail, cancel an unpaid one.

Read through `actor_ids_for`, so orders bought from an account later merged into this one
still show (the buyer column stays on the shell, like `Payment.member`). Only spaces whose
`shop` module is on; a space switched off keeps the rows but hides them (#95).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.staff_identity import actor_ids_for

from .models import ShopOrder
from .serializers_public import BuyerOrderSerializer, ShopErrorSerializer

TAGS = ["Member shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 409)}


def my_orders(user):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    spaces = servable_queryset(Makerspace.objects.filter(enabled_modules__contains=["shop"])).values("pk")
    return (ShopOrder.objects.filter(buyer_id__in=actor_ids_for(user), makerspace_id__in=spaces)
            .select_related("makerspace", "pickup_event").prefetch_related("lines"))


class MemberShopOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, parameters=[OpenApiParameter("makerspace_id", int, OpenApiParameter.QUERY),
                                          OpenApiParameter("page", int, OpenApiParameter.QUERY)],
                   responses={200: BuyerOrderSerializer(many=True), **ERRORS})
    def get(self, request):
        rows = my_orders(request.user)
        if request.query_params.get("makerspace_id", "").isdigit():
            rows = rows.filter(makerspace_id=int(request.query_params["makerspace_id"]))
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows.order_by("-created_at", "-pk"), request)
        return paginator.get_paginated_response(BuyerOrderSerializer(page, many=True).data)


class MemberShopOrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, responses={200: BuyerOrderSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(BuyerOrderSerializer(get_object_or_404(my_orders(request.user), pk=pk)).data)


class MemberShopOrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, request=None, responses={200: BuyerOrderSerializer, **ERRORS},
                   summary="Cancel my unpaid order (its stock goes back; nothing is charged)")
    def post(self, request, pk):
        from .services_orders import cancel_unpaid
        order = cancel_unpaid(get_object_or_404(my_orders(request.user), pk=pk), actor=request.user)
        return Response(BuyerOrderSerializer(order).data)
