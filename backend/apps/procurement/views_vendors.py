"""Vendor records and "mark bought" (#94) for the To-Buy list."""

from decimal import Decimal

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.folded_capabilities import require_capability
from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement import services_vendors
from apps.procurement.models import Vendor
from apps.procurement.serializers import ToBuyItemSerializer
from apps.procurement.services_bought import mark_bought
from apps.procurement.views_common import PROCUREMENT_ERROR_RESPONSES
from apps.procurement.views_items import _scoped_makerspace
from apps.procurement.views_move import ToBuyMoveBaseView


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "contact_name", "email", "phone", "website", "notes", "is_archived",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class MarkBoughtSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    method = serializers.ChoiceField(choices=LedgerEntry.Method.choices)
    reference = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    receipt_id = serializers.IntegerField(required=False, allow_null=True, min_value=1,
                                         help_text="An evidence upload from the finance receipt presign "
                                                   "(photo or PDF), promoted exactly once.")
    vendor_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    vendor_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    refill_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True,
                                             min_value=Decimal("0.01"),
                                             help_text="Grams received, for an item raised by a machine consumable.")
    entry_date = serializers.DateField(required=False, allow_null=True)


def _vendor_space(request, makerspace_id):
    space = _scoped_makerspace(request.user, makerspace_id)
    require_capability(space, services_vendors.FEATURE)
    if not services_vendors.may_manage(request.user, space.pk):
        raise PermissionDenied()
    return space


@extend_schema(tags=["Procurement"])
class VendorListCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(summary="List vendors",
                   parameters=[OpenApiParameter("archived", bool, required=False)],
                   responses={200: VendorSerializer(many=True), **PROCUREMENT_ERROR_RESPONSES})
    def get(self, request, makerspace_id):
        space = _vendor_space(request, makerspace_id)
        rows = Vendor.objects.filter(makerspace=space)
        if request.query_params.get("archived") not in ("1", "true"):
            rows = rows.filter(is_archived=False)
        return Response(VendorSerializer(rows[:500], many=True).data)

    @extend_schema(summary="Add a vendor", request=VendorSerializer,
                   responses={201: VendorSerializer, **PROCUREMENT_ERROR_RESPONSES})
    def post(self, request, makerspace_id):
        space = _vendor_space(request, makerspace_id)
        payload = VendorSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        vendor = services_vendors.create_vendor(request.user, space, payload.validated_data)
        return Response(VendorSerializer(vendor).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Procurement"])
class VendorDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(summary="Edit or archive a vendor", request=VendorSerializer,
                   responses={200: VendorSerializer, **PROCUREMENT_ERROR_RESPONSES})
    def patch(self, request, makerspace_id, pk):
        space = _vendor_space(request, makerspace_id)
        vendor = get_object_or_404(Vendor.objects.filter(makerspace=space), pk=pk)
        payload = VendorSerializer(vendor, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        vendor = services_vendors.update_vendor(request.user, vendor, payload.validated_data)
        return Response(VendorSerializer(vendor).data)


@extend_schema(tags=["Procurement"])
class ToBuyMarkBoughtView(ToBuyMoveBaseView):
    @extend_schema(
        summary="Mark a To-Buy item bought",
        description=("Records what was paid in the finance ledger (once per item), marks the item received "
                     "and puts the stock back up when it came from a consumable. Inventory rows: the Space "
                     "Manager or the Inventory Manager; machine rows: the Machine Manager for that machine "
                     "type or the Space Manager. Nothing is paid out by this call."),
        request=MarkBoughtSerializer, responses={200: ToBuyItemSerializer, **PROCUREMENT_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        item = self.get_item(pk)
        payload = MarkBoughtSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        if not data.get("currency"):
            from apps.payments.models import MakerspacePaymentSettings
            data["currency"] = MakerspacePaymentSettings.for_makerspace(item.makerspace).default_currency
        if data.get("vendor_id") is not None:
            require_capability(item.makerspace, services_vendors.FEATURE)
        mark_bought(request.user, item, **data)
        return self.serialize_item(pk)
