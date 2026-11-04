"""The front desk (`SELL_SHOP`): quote, sell, look up a member, and the cash drawer.

Cash sessions need `shop.cash_up`. A seller sees the sessions they opened; a shop manager
sees every session of the space (Q-S10 (c)). Product images are public-bucket images with
the usual presign -> attach flow (`MANAGE_SHOP`).
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff

from .gates import MANAGE, SELL, require_feature, staff_space
from .models import ShopCashSession
from .serializers_public import ShopErrorSerializer, ShopQuoteSerializer
from .serializers_staff import (
    ShopCashCloseSerializer, ShopCashOpenSerializer, ShopCashSessionSerializer, ShopMemberHitSerializer, ShopPosQuoteSerializer,
    ShopPosSaleSerializer, ShopStaffOrderSerializer,
)
from .views_staff_catalogue import PAGE, page

TAGS = ["Admin shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 409)}


def _member(space, member_id):
    if not member_id:
        return None
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership

    if not MakerspaceMembership.objects.filter(makerspace=space, user_id=member_id, status="active").exists():
        from .errors import ShopRefused
        raise ShopRefused("not_found", "That person is not a member of this space.")
    return User.objects.get(pk=member_id)


class ShopPosQuoteView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopPosQuoteSerializer, responses={200: ShopQuoteSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from .pricing import priced_basket, quote_payload
        space = staff_space(request.user, makerspace_id, SELL)
        body = ShopPosQuoteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        member = _member(space, body.validated_data.get("member_id"))
        basket = priced_basket(space, body.validated_data["lines"], person=member, public=False)
        return Response(ShopQuoteSerializer(quote_payload(space, basket)).data)


class ShopPosSaleView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopPosSaleSerializer, responses={201: ShopStaffOrderSerializer, **ERRORS},
                   summary="Sell at the desk: stock out, payment recorded (cash, UPI or card), handed over")
    def post(self, request, makerspace_id):
        from .services_pos import pos_sale
        space = staff_space(request.user, makerspace_id, SELL)
        body = ShopPosSaleSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        order = pos_sale(space, actor=request.user, lines=data["lines"], member=_member(space, data.get("member_id")),
                         method=data["method"], reference=data.get("reference", ""),
                         received_at=data.get("received_at"), digest=data.get("quote_digest"),
                         receipt_email=data.get("receipt_email", ""))
        return Response(ShopStaffOrderSerializer(order, context={"request": request}).data, status=201)


class ShopMemberLookupView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=[OpenApiParameter("q", str, OpenApiParameter.QUERY)],
                   responses={200: ShopMemberHitSerializer(many=True), **ERRORS},
                   summary="Find a member of this space by name or username (for member prices)")
    def get(self, request, makerspace_id):
        from apps.makerspaces.models import MakerspaceMembership
        space = staff_space(request.user, makerspace_id, SELL)
        term = (request.query_params.get("q") or "").strip()[:80]
        if len(term) < 2:
            return Response([])
        rows = MakerspaceMembership.objects.filter(makerspace=space, status="active").filter(
            Q(user__username__icontains=term) | Q(user__display_name__icontains=term)).select_related("user")[:10]
        return Response([{"id": row.user_id, "name": row.user.get_full_name() or row.user.display_name
                          or row.user.username} for row in rows])


class ShopCashSessionListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=PAGE, responses={200: ShopCashSessionSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = require_feature(staff_space(request.user, makerspace_id, SELL), "shop.cash_up")
        rows = ShopCashSession.objects.filter(makerspace=space)
        if not rbac.can(request.user, MANAGE, space.pk):
            rows = rows.filter(opened_by=request.user)
        return page(request, rows, ShopCashSessionSerializer)

    @extend_schema(tags=TAGS, request=ShopCashOpenSerializer, responses={201: ShopCashSessionSerializer, **ERRORS},
                   summary="Open the cash drawer with a float")
    def post(self, request, makerspace_id):
        from .services_cash import open_cash
        space = require_feature(staff_space(request.user, makerspace_id, SELL), "shop.cash_up")
        body = ShopCashOpenSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        session = open_cash(space, actor=request.user, opening_float=body.validated_data["opening_float"])
        return Response(ShopCashSessionSerializer(session).data, status=201)


def _session(request, pk, action=SELL):
    session = get_object_or_404(ShopCashSession.objects.select_related("makerspace"), pk=pk)
    require_feature(staff_space(request.user, session.makerspace_id, action), "shop.cash_up")
    return session


class ShopCashSessionCloseView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=ShopCashCloseSerializer, responses={200: ShopCashSessionSerializer, **ERRORS},
                   summary="Close with the counted cash (a second person confirms when the check is on)")
    def post(self, request, pk):
        from .services_cash import close_cash
        body = ShopCashCloseSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(ShopCashSessionSerializer(close_cash(_session(request, pk), actor=request.user,
                                                         **body.validated_data)).data)


class ShopCashSessionConfirmView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=None, responses={200: ShopCashSessionSerializer, **ERRORS},
                   summary="Second-person check of a cash-up")
    def post(self, request, pk):
        from .services_cash import confirm_cash
        return Response(ShopCashSessionSerializer(confirm_cash(_session(request, pk), actor=request.user)).data)
