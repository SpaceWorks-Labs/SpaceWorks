"""What a profile row may draw stock from (decision 341): the space's pools for the type, and inventory items.

Read-only, behind the same per-type authority as editing the profile. Pools are listed with their unit so
the editor only offers ones the row's unit can draw from; items are searched by name (at most 20).
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.inventory.models import InventoryProduct

from . import consumable_profile_services as profiles
from .views_consumable_profiles import ERRORS, TAGS


class ConsumableStockPoolSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    unit = serializers.CharField()
    remaining = serializers.DecimalField(max_digits=12, decimal_places=2)


class ConsumableStockItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ConsumableStockOptionsSerializer(serializers.Serializer):
    pools = ConsumableStockPoolSerializer(many=True)
    products = ConsumableStockItemSerializer(many=True)


class TypeConsumableStockOptionsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Stock a machine type's consumables may draw from",
                   parameters=[OpenApiParameter("q", str, description="Inventory item name search.")],
                   responses={200: ConsumableStockOptionsSerializer, **ERRORS})
    def get(self, request, makerspace_id, type_id):
        space, machine_type = profiles.space_and_type(request.user, makerspace_id, type_id, write=True)
        pools = [{"id": pool.pk, "label": pool.label, "unit": pool.unit, "remaining": pool.remaining_grams}
                 for pool in profiles.pools_for(space, machine_type).order_by("material", "id")[:200]]
        query = str(request.query_params.get("q") or "").strip()[:100]
        products = []
        if query and rbac.can(request.user, rbac.Action.VIEW_INVENTORY, space.pk):
            rows = rbac.scope_verified_tenant(InventoryProduct.objects.all(), space).filter(name__icontains=query)
            products = [{"id": row.pk, "name": row.name} for row in rows.order_by("name", "id")[:20]]
        return Response(ConsumableStockOptionsSerializer({"pools": pools, "products": products}).data)
