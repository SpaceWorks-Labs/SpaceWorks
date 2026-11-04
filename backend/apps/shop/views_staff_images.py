"""A product's public image (`MANAGE_SHOP`): presign, attach (finalize + sniff), clear.

The same public-image rules as every other public image: a presigned upload to the
staging key, finalized and sniffed before it is attached, counted against the space's
storage, and the old object released when replaced. Keys live under `shop/<space>/`.
"""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_inventory import (
    PublicImageAttachRequestSerializer, PublicImageUploadRequestSerializer, PublicImageUploadResponseSerializer,
)
from apps.audit import services as audit
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.inventory import public_image_storage

from .gates import MANAGE
from .serializers_public import ShopErrorSerializer
from .serializers_staff import ProductSerializer
from .views_staff_catalogue import product_for

TAGS = ["Admin shop"]
ERRORS = {code: ShopErrorSerializer for code in (400, 403, 404, 503)}


def _reject(object_key, message):
    public_image_storage.delete_object(object_key)
    public_image_storage.delete_object(public_image_storage.staging_key(object_key))
    raise ValidationError({"object_key": message})


class ShopProductImageView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=PublicImageUploadRequestSerializer,
                   responses={201: PublicImageUploadResponseSerializer, **ERRORS})
    def post(self, request, pk):
        product = product_for(request, pk, MANAGE)
        body = PublicImageUploadRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        ext = public_image_storage.ext_for(body.validated_data["content_type"], body.validated_data["filename"])
        object_key = public_image_storage.build_object_key("shop", product.makerspace_id, ext)
        try:
            upload = public_image_storage.presigned_upload(object_key, body.validated_data["content_type"])
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(PublicImageUploadResponseSerializer({"object_key": object_key, **upload}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(tags=TAGS, request=PublicImageAttachRequestSerializer, responses={200: ProductSerializer, **ERRORS})
    @transaction.atomic
    def put(self, request, pk):
        from apps.makerspaces.limits import add_storage
        product = product_for(request, pk, MANAGE)
        body = PublicImageAttachRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        object_key = body.validated_data["object_key"]
        if not object_key.startswith(f"shop/{product.makerspace_id}/") or \
                not public_image_storage.is_safe_object_key(object_key):
            raise ValidationError({"object_key": "Image object key is outside this shop."})
        if type(product).objects.filter(makerspace_id=product.makerspace_id, image_key=object_key).exclude(
                pk=product.pk).exists():
            raise ValidationError({"object_key": "This image is already in use."})
        try:
            result = public_image_storage.finalize_upload(object_key)
            if result.status != "ok":
                _reject(object_key, public_image_storage.finalize_error_message(result))
            if not public_image_storage.sniff_is_valid_image(object_key):
                _reject(object_key, "Uploaded file is not a valid image.")
        except StorageUnavailable:
            return storage_unavailable_response()
        old_key = product.image_key
        if object_key != old_key:
            add_storage(product.makerspace, result.size)
        product.image_key = object_key
        product.save(update_fields=["image_key", "updated_at"])
        if old_key and old_key != object_key:
            public_image_storage.release_public_image_on_commit(product.makerspace, old_key)
        audit.record(request.user, "shop.product_image_set", makerspace=product.makerspace, target=product,
                     meta={"product_id": product.pk})
        return Response(ProductSerializer(product, context={"request": request}).data)

    @extend_schema(tags=TAGS, request=None, responses={200: ProductSerializer, **ERRORS})
    def delete(self, request, pk):
        product = product_for(request, pk, MANAGE)
        if product.image_key:
            old_key, product.image_key = product.image_key, ""
            product.save(update_fields=["image_key", "updated_at"])
            public_image_storage.release_public_image_on_commit(product.makerspace, old_key)
            audit.record(request.user, "shop.product_image_cleared", makerspace=product.makerspace,
                         target=product, meta={"product_id": product.pk})
        return Response(ProductSerializer(product, context={"request": request}).data)
