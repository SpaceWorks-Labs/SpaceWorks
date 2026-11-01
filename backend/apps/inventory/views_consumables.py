"""Staff consumables screen API (MI-40): the merged list and the take-and-go use log."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.inventory import availability
from apps.inventory.consumables import consumable_rows
from apps.inventory.models import InventoryProduct
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404)}


class ConsumableRowSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["item", "machine", "pool"])
    id = serializers.IntegerField()
    name = serializers.CharField()
    machine_id = serializers.IntegerField(allow_null=True)
    machine_name = serializers.CharField(allow_blank=True)
    unit = serializers.CharField()
    remaining = serializers.CharField()
    threshold = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=["ok", "low"])
    open_to_buy_id = serializers.IntegerField(allow_null=True)


class ConsumableUseSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=100000)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class ConsumablePagination(PageNumberPagination):
    page_size = 24


def _space(actor, makerspace_id):
    space = get_object_or_404(rbac.scope_by_makerspace(actor, Makerspace.objects.all(), makerspace_field="id"),
                              pk=makerspace_id)
    require_module(space, "staff_admin")
    from apps.makerspaces.folded_capabilities import require_capability
    require_capability(space, "inventory.consumables")
    return space


class ConsumableListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin inventory"], summary="List consumables across items, machines and pools",
        parameters=[OpenApiParameter("status", str, enum=["low", "ok"], required=False)],
        responses={200: ConsumableRowSerializer(many=True), **ERRORS},
    )
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        rows = consumable_rows(request.user, space, status=request.query_params.get("status"))
        paginator = ConsumablePagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(ConsumableRowSerializer(page, many=True).data)


class ConsumableUseView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin inventory"], summary="Log units of an item consumable as used",
        request=ConsumableUseSerializer, responses={200: ConsumableRowSerializer, **ERRORS},
    )
    def post(self, request, makerspace_id, pk):
        space = _space(request.user, makerspace_id)
        require_action(request.user, rbac.Action.EDIT_INVENTORY, space.pk)
        product = get_object_or_404(rbac.scope_by_action(
            request.user, rbac.Action.EDIT_INVENTORY,
            InventoryProduct.objects.filter(makerspace=space, is_archived=False)), pk=pk)
        if not product.is_consumable:
            raise PermissionDenied("Only consumables can be logged as used.")
        serializer = ConsumableUseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data["note"].strip()
        try:
            product = availability.consume_available(
                product, serializer.validated_data["quantity"],
                reason=f"Consumable used{': ' + note if note else ''}", actor=request.user)
        except availability.InsufficientStock as exc:
            raise ValidationError({"quantity": str(exc)}) from exc
        row = next((row for row in consumable_rows(request.user, space)
                    if row["source"] == "item" and row["id"] == product.pk), None)
        return Response(ConsumableRowSerializer(row).data)
