"""Product-scoped, staff-authorized candidate sources for a linked use."""
from django.db.models import F, IntegerField, Q, Sum, Value
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.hardware_requests.loan_context_access import authorized_request_queryset
from apps.inventory.models import InventoryProduct
from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan, EquipmentKitAllocation
from apps.inventory.views_consumables import _space
from apps.makerspaces.guards import SurfaceOff


class ConsumableSourceSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["allocation", "plan"])
    id = serializers.IntegerField()
    planned_quantity = serializers.IntegerField()
    used_quantity = serializers.IntegerField()


class ConsumableSourcePage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ConsumableSourceSerializer(many=True)


class _Page(PageNumberPagination):
    page_size = 24


def _rows(queryset, kind, product_id):
    table = queryset.model._meta.db_table
    # The table name is model-owned, not user input. Only validated quantities
    # are projected; malformed historical JSON contributes zero.
    planned = RawSQL(
        "CASE WHEN jsonb_typeof(\"%s\".lines) = 'array' THEN "
        "COALESCE((SELECT CASE WHEN (line.value->>'quantity_per_person') ~ '^[1-9][0-9]?$' "
        "THEN (line.value->>'quantity_per_person')::integer ELSE 0 END "
        "FROM jsonb_array_elements(\"%s\".lines) AS line(value) "
        "WHERE line.value->>'product_id' = %%s AND line.value->>'kind' = 'consumable' LIMIT 1), 0) "
        "ELSE 0 END" % (table, table), [str(product_id)], output_field=IntegerField(),
    )
    return queryset.filter(lines__contains=[{"product_id": product_id, "kind": "consumable"}]).annotate(
        kind=Value(kind), planned_quantity=planned,
        used_quantity=-Coalesce(Sum(
            "equipmentconsumableusereceipt__adjustment__delta_available",
            filter=Q(equipmentconsumableusereceipt__product_id=product_id),
        ), 0),
    ).order_by().values("id", "kind", "planned_quantity", "used_quantity")


def _live_plans(maker):
    """Plans that stay visible: loan plans always; event/booking plans only while that module is on."""
    from apps.makerspaces.platform import module_enabled
    from apps.separability.tombstones import app_is_tombstoned

    plans = EquipmentConsumablePlan.objects.filter(makerspace=maker)
    for app, module, reverse in (
        ("events", "events", "eventconsumableplancontext"),
        ("bookings", "bookings", "bookingconsumableplancontext"),
    ):
        if not app_is_tombstoned(app) and not module_enabled(maker, module):
            plans = plans.exclude(**{f"{reverse}__isnull": False})
    return plans


class ConsumableSourceListView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number.")],
                   responses={200: ConsumableSourcePage, 401: OpenApiResponse(description="Authentication required."),
                              403: OpenApiResponse(description="Forbidden."),
                              404: OpenApiResponse(description="Product or feature unavailable.")})
    def get(self, request, makerspace_id, pk):
        maker = _space(request.user, makerspace_id)
        require_action(request.user, rbac.Action.EDIT_INVENTORY, maker.pk)
        product = get_object_or_404(rbac.scope_by_action(
            request.user, rbac.Action.EDIT_INVENTORY,
            InventoryProduct.objects.filter(makerspace=maker, is_consumable=True),
        ), pk=pk)
        try:
            allowed_requests = authorized_request_queryset(request.user, maker).values("pk")
            allocations = EquipmentKitAllocation.objects.filter(makerspace=maker, request_id__in=allowed_requests)
        except SurfaceOff:
            allocations = EquipmentKitAllocation.objects.none()
        plans = _live_plans(maker)
        rows = _rows(allocations, "allocation", product.pk).union(
            _rows(plans, "plan", product.pk), all=True,
        ).order_by("kind", "id")
        paginator = _Page()
        return paginator.get_paginated_response(ConsumableSourceSerializer(
            paginator.paginate_queryset(rows, request), many=True,
        ).data)
