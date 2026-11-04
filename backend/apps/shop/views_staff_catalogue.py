"""Staff catalogue and stock (`VIEW_SHOP` reads, `MANAGE_SHOP` writes), plus the shop settings.

Each row is resolved through its own space and the actor's authority there (rbac), so an
id from another space answers 404. Settings writes go through L17's settings authority
(`assert_setting_write`, module `shop`): the Space Manager, or the Shop Manager by its
fixed exception (#137).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from .gates import MANAGE, VIEW, staff_space
from .models import ShopProduct, ShopSettings, ShopStockMovement, ShopVariant
from .serializers_public import ShopErrorSerializer
from .serializers_staff import (
    MovementSerializer, ProductSerializer, ShopSettingsSerializer, StockMoveSerializer, VariantSerializer,
)

TAGS = ["Admin shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 409)}
PAGE = [OpenApiParameter("page", int, OpenApiParameter.QUERY)]


def page(request, rows, serializer, **context):
    paginator = PageNumberPagination()
    paginator.page_size = 24
    chunk = paginator.paginate_queryset(rows, request)
    return paginator.get_paginated_response(serializer(chunk, many=True, context={"request": request,
                                                                                  **context}).data)


def product_for(request, pk, action=VIEW):
    product = get_object_or_404(ShopProduct.objects.select_related("makerspace"), pk=pk)
    staff_space(request.user, product.makerspace_id, action)
    return product


def _write_data(validated):
    data = dict(validated)
    if "components_in" in data:
        data["components"] = data.pop("components_in")
    return data


class ShopProductListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=[*PAGE, OpenApiParameter("archived", bool, OpenApiParameter.QUERY)],
                   responses={200: ProductSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, VIEW)
        rows = ShopProduct.objects.filter(makerspace=space).prefetch_related("variants", "components")
        rows = rows.filter(archived_at__isnull=request.query_params.get("archived") != "true")
        return page(request, rows, ProductSerializer)

    @extend_schema(tags=TAGS, request=ProductSerializer, responses={201: ProductSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        from .services_catalogue import save_product
        space = staff_space(request.user, makerspace_id, MANAGE)
        body = ProductSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        product = save_product(space, _write_data(body.validated_data), actor=request.user)
        return Response(ProductSerializer(product, context={"request": request}).data, status=201)


class ShopProductDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, responses={200: ProductSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(ProductSerializer(product_for(request, pk), context={"request": request}).data)

    @extend_schema(tags=TAGS, request=ProductSerializer, responses={200: ProductSerializer, **ERRORS})
    def patch(self, request, pk):
        from .services_catalogue import save_product
        product = product_for(request, pk, MANAGE)
        body = ProductSerializer(product, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        product = save_product(product.makerspace, _write_data(body.validated_data), actor=request.user,
                               product=product)
        return Response(ProductSerializer(product, context={"request": request}).data)

    @extend_schema(tags=TAGS, request=None, responses={200: ProductSerializer, **ERRORS},
                   summary="Archive a product and its variants (orders keep them)")
    def delete(self, request, pk):
        from .services_catalogue import archive_product
        product = archive_product(product_for(request, pk, MANAGE), actor=request.user)
        return Response(ProductSerializer(product, context={"request": request}).data)


class ShopVariantDetailView(APIView):
    permission_classes = [IsActiveStaff]

    def variant(self, request, pk, action):
        variant = get_object_or_404(ShopVariant.objects.select_related("makerspace", "product"), pk=pk)
        staff_space(request.user, variant.makerspace_id, action)
        return variant

    @extend_schema(tags=TAGS, request=None, responses={200: VariantSerializer, **ERRORS},
                   summary="Archive one variant")
    def delete(self, request, pk):
        from .services_catalogue import archive_variant
        return Response(VariantSerializer(archive_variant(self.variant(request, pk, MANAGE), actor=request.user)).data)


class ShopVariantStockView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=StockMoveSerializer, responses={200: VariantSerializer, **ERRORS},
                   summary="Restock, or correct the count (count, damage, internal use)")
    def post(self, request, pk):
        from .services_catalogue import move_stock
        variant = get_object_or_404(ShopVariant.objects.select_related("makerspace"), pk=pk)
        staff_space(request.user, variant.makerspace_id, MANAGE)
        body = StockMoveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = move_stock(variant, actor=request.user, **body.validated_data)
        return Response(VariantSerializer(row).data)


class ShopMovementListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=[*PAGE, OpenApiParameter("variant_id", int, OpenApiParameter.QUERY)],
                   responses={200: MovementSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, VIEW)
        rows = ShopStockMovement.objects.filter(makerspace=space).select_related("actor")
        if request.query_params.get("variant_id", "").isdigit():
            rows = rows.filter(variant_id=int(request.query_params["variant_id"]))
        return page(request, rows, MovementSerializer)


class ShopSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, responses={200: ShopSettingsSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, VIEW)
        return Response(ShopSettingsSerializer(ShopSettings.for_makerspace(space)).data)

    @extend_schema(tags=TAGS, request=ShopSettingsSerializer, responses={200: ShopSettingsSerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        from .settings_service import update_settings
        space = staff_space(request.user, makerspace_id, VIEW)
        row = ShopSettings.for_makerspace(space)
        body = ShopSettingsSerializer(row, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        return Response(ShopSettingsSerializer(update_settings(space, row, body.validated_data,
                                                               actor=request.user)).data)
