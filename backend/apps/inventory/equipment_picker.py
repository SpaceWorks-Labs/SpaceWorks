"""Minimal product projection; by default no counts or storage metadata.

A caller that has already proven inventory-view authority may ask for the
availability owner's stored `available_quantity` and the earliest due-back of
the product's open loans. Nothing is recomputed here.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from apps.inventory import public_image_storage
from apps.inventory.requestable_products import requestable_products


class RequestableProductSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    event_only = serializers.BooleanField(read_only=True, help_text="Lendable only through an event (221b).")
    image_url = serializers.SerializerMethodField()
    # Present only for inventory-view staff on the event equipment picker.
    available_quantity = serializers.IntegerField(read_only=True, required=False)
    next_due_back_at = serializers.DateTimeField(read_only=True, required=False, allow_null=True)

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_image_url(self, product):
        return public_image_storage.public_url(product.image_key) or None

    def to_representation(self, product):
        data = super().to_representation(product)
        due = self.context.get("due_back")
        if due is None:
            data.pop("available_quantity", None)
            data.pop("next_due_back_at", None)
        else:
            data["available_quantity"] = product.available_quantity
            value = due.get(product.pk)
            data["next_due_back_at"] = value.isoformat() if value else None
        return data


class RequestableProductPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RequestableProductSerializer(many=True)


class PickerPage(PageNumberPagination):
    page_size = 24


def _due_back(products):
    from django.db.models import Min
    from apps.hardware_requests.models import HardwareRequestItem
    rows = HardwareRequestItem.objects.filter(
        product_id__in=[product.pk for product in products],
        request__status__in=("issued", "partially_returned"), request__return_due_at__isnull=False,
    ).values("product_id").annotate(first=Min("request__return_due_at"))
    return {row["product_id"]: row["first"] for row in rows}


def product_page(request, maker, *, availability=False, event_context=False):
    rows = requestable_products(maker, event_context=event_context).order_by("pk")
    paginator = PickerPage()
    page = paginator.paginate_queryset(rows, request)
    context = {"due_back": _due_back(page)} if availability else {}
    return paginator.get_paginated_response(RequestableProductSerializer(page, many=True, context=context).data)
