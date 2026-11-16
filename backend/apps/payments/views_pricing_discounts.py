"""Member discount rules: list, create, change, archive (lane L15, A3/A4).

Space Manager only for writes (space-wide money policy, never delegable); finance staff
may read. 404 while `charges.pricing` or `charges.discounts` is off. Rules are archived,
never deleted.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors
from apps.payments.models_pricing_rules import PriceDiscount
from apps.payments.pricing import discount_services
from apps.payments.pricing.discounts import DISCOUNTS_FEATURE
from apps.payments.pricing.errors import PricingDisabled
from apps.payments.pricing.http import require_pricing, space_for
from apps.payments.pricing.serializers_rules import PriceDiscountSerializer

TAGS = ["Pricing"]
WRITE_ERRORS = errors(400, 401, 403, 404, 423, e403="Space Manager only (`setting_not_delegated`).",
                      e400="`discount_invalid` or a field error.")


def _space(request, makerspace_id):
    space = space_for(request.user, makerspace_id, rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_FINANCE)
    require_pricing(space)
    if not feature_enabled(space, DISCOUNTS_FEATURE):
        raise PricingDisabled(gettext("Member discounts are switched off for this space."))
    return space


def _context(request):
    return {"request": request}


class DiscountListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List member discount rules",
                   parameters=[OpenApiParameter("archived", bool, description="Include archived rules.")],
                   responses={200: PriceDiscountSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        rules = PriceDiscount.objects.filter(makerspace=space).select_related("plan", "member")
        if request.query_params.get("archived") not in ("1", "true"):
            rules = rules.filter(archived_at__isnull=True)
        return Response(PriceDiscountSerializer(rules, many=True, context=_context(request)).data)

    @extend_schema(tags=TAGS, summary="Create a member discount rule",
                   description="One best automatic discount applies per quote (all members, a plan's "
                               "members, or one member), then an event promo code on top; nothing else stacks. "
                               "Deposits, late, damage and lost fees are never discounted unless named.",
                   request=PriceDiscountSerializer, responses={201: PriceDiscountSerializer, **WRITE_ERRORS})
    def post(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        body = PriceDiscountSerializer(data=request.data, context={"makerspace": space})
        body.is_valid(raise_exception=True)
        rule = discount_services.create_discount(request.user, space, body.validated_data)
        return Response(PriceDiscountSerializer(rule, context=_context(request)).data, status=201)


class DiscountDetailView(APIView):
    permission_classes = [IsActiveStaff]

    def _rule(self, request, makerspace_id, discount_id):
        space = _space(request, makerspace_id)
        return get_object_or_404(PriceDiscount.objects.select_related("plan", "member"), pk=discount_id,
                                 makerspace=space)

    @extend_schema(tags=TAGS, summary="Change a member discount rule", request=PriceDiscountSerializer,
                   responses={200: PriceDiscountSerializer, **WRITE_ERRORS})
    def patch(self, request, makerspace_id, discount_id):
        rule = self._rule(request, makerspace_id, discount_id)
        body = PriceDiscountSerializer(rule, data=request.data, partial=True, context={"makerspace": rule.makerspace})
        body.is_valid(raise_exception=True)
        rule = discount_services.update_discount(request.user, rule, body.validated_data)
        return Response(PriceDiscountSerializer(rule, context=_context(request)).data)


class DiscountArchiveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Archive a member discount rule", request=None,
                   description="Archived rules stop applying; quotes already frozen keep naming them.",
                   responses={200: PriceDiscountSerializer, **WRITE_ERRORS})
    def post(self, request, makerspace_id, discount_id):
        space = _space(request, makerspace_id)
        rule = get_object_or_404(PriceDiscount, pk=discount_id, makerspace=space)
        rule = discount_services.archive_discount(request.user, rule)
        return Response(PriceDiscountSerializer(rule, context=_context(request)).data)
