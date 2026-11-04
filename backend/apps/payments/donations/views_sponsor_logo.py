"""A sponsor's public logo, through the public image pipeline (presign, finalize, sniff, quota).

The key is pinned to `sponsor/<space>/`, so only another sponsor of the same space could claim
it; it is charged to storage once, released when replaced or cleared, collected by the space
purge and counted by the storage reconciler, and declared in the backup ownership registry.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_inventory import (
    PublicImageAttachRequestSerializer,
    PublicImageUploadRequestSerializer,
    PublicImageUploadResponseSerializer,
)
from apps.audit import services as audit
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.inventory import public_image_storage as images
from apps.makerspaces.limits import add_storage

from .models import Sponsor
from .serializers_sponsors import SponsorSerializer
from .views_sponsors import ERRORS, TAG, _row


def _discard(key):
    images.delete_object(key)
    images.delete_object(images.staging_key(key))


class SponsorLogoView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAG, summary="Create a sponsor logo upload URL", request=PublicImageUploadRequestSerializer,
                   responses={201: PublicImageUploadResponseSerializer, 503: OpenApiResponse(), **ERRORS})
    def post(self, request, makerspace_id, pk):
        sponsor = _row(request, Sponsor, makerspace_id, pk, record=True)
        payload = PublicImageUploadRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        content_type = payload.validated_data["content_type"]
        key = images.build_object_key("sponsor", sponsor.makerspace_id,
                                      images.ext_for(content_type, payload.validated_data["filename"]))
        try:
            upload = images.presigned_upload(key, content_type)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(PublicImageUploadResponseSerializer({"object_key": key, **upload}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(tags=TAG, summary="Attach an uploaded logo to a sponsor", description="Audited `sponsor.logo_updated`.",
                   request=PublicImageAttachRequestSerializer,
                   responses={200: SponsorSerializer, 503: OpenApiResponse(), **ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id, pk):
        sponsor = _row(request, Sponsor, makerspace_id, pk, record=True)
        payload = PublicImageAttachRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        key = payload.validated_data["object_key"]
        if not key.startswith(f"sponsor/{sponsor.makerspace_id}/") or not images.is_safe_object_key(key):
            raise ValidationError({"object_key": "Image object key is outside this makerspace."})
        if Sponsor.objects.filter(logo_key=key).exclude(pk=sponsor.pk).exists():
            raise ValidationError({"object_key": "This image is already in use."})
        try:
            result = images.finalize_upload(key)
            if result.status != "ok":
                if result.status in {"empty", "too_large"}:
                    _discard(key)
                raise ValidationError({"object_key": images.finalize_error_message(result)})
            if not images.sniff_is_valid_image(key):
                _discard(key)
                raise ValidationError({"object_key": "Uploaded file is not a valid image."})
        except StorageUnavailable:
            return storage_unavailable_response()
        sponsor = Sponsor.objects.select_for_update().select_related("makerspace").get(pk=sponsor.pk)
        if key != sponsor.logo_key:
            add_storage(sponsor.makerspace, result.size)
            if sponsor.logo_key:
                images.release_public_image_on_commit(sponsor.makerspace, sponsor.logo_key)
        sponsor.logo_key = key
        sponsor.save(update_fields=["logo_key", "updated_at"])
        audit.record(request.user, "sponsor.logo_updated", makerspace=sponsor.makerspace, target=sponsor,
                     meta={"sponsor_id": sponsor.pk})
        return Response(SponsorSerializer(sponsor, context={"request": request}).data)

    @extend_schema(tags=TAG, summary="Clear a sponsor's logo", description="Audited `sponsor.logo_removed`.",
                   request=None, responses={200: SponsorSerializer, **ERRORS})
    @transaction.atomic
    def delete(self, request, makerspace_id, pk):
        sponsor = _row(request, Sponsor, makerspace_id, pk, record=True)
        sponsor = Sponsor.objects.select_for_update().select_related("makerspace").get(pk=sponsor.pk)
        if sponsor.logo_key:
            images.release_public_image_on_commit(sponsor.makerspace, sponsor.logo_key)
            sponsor.logo_key = ""
            sponsor.save(update_fields=["logo_key", "updated_at"])
            audit.record(request.user, "sponsor.logo_removed", makerspace=sponsor.makerspace, target=sponsor,
                         meta={"sponsor_id": sponsor.pk})
        return Response(SponsorSerializer(sponsor, context={"request": request}).data)
