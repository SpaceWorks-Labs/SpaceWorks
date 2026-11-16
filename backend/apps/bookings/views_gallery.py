"""Staff place-photo gallery API for a bookable space (OpenAPI-documented)."""

from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable

from . import booking_authority, services_gallery, storage
from .serializers_admin import SpaceImagePresignRequestSerializer, SpaceImagePresignResponseSerializer
from .views_admin_space_detail import IMAGE_ERROR_RESPONSES


class SpacePhotoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    url = serializers.SerializerMethodField()
    caption = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def get_url(self, obj) -> str:
        return storage.public_url(obj.object_key)


class SpacePhotoListSerializer(serializers.Serializer):
    max_photos = serializers.IntegerField()
    can_edit = serializers.BooleanField()
    results = SpacePhotoSerializer(many=True)


class SpacePhotoAttachSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=500)
    caption = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class SpacePhotoUpdateSerializer(serializers.Serializer):
    caption = serializers.CharField(max_length=200, allow_blank=True)


class SpacePhotoOrderSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=50)


def _listing(request, space):
    from .models_gallery import MAX_PHOTOS_PER_SPACE
    return Response(SpacePhotoListSerializer({
        "max_photos": MAX_PHOTOS_PER_SPACE,
        "can_edit": booking_authority.can(request.user, space, "edit_details"),
        "results": list(space.photos.all()),
    }).data)


class SpacePhotoListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="List a space's place photos",
                   responses={200: SpacePhotoListSerializer, **IMAGE_ERROR_RESPONSES})
    def get(self, request, pk):
        return _listing(request, booking_authority.get_space(request.user, pk, "view"))

    @extend_schema(tags=["Admin bookings"], summary="Finalize an uploaded photo and add it to the gallery",
                   request=SpacePhotoAttachSerializer,
                   responses={201: SpacePhotoSerializer, **IMAGE_ERROR_RESPONSES})
    def post(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        body = SpacePhotoAttachSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        key = body.validated_data["object_key"]
        if not storage.is_owned_object_key(space, key) or not storage.has_allowed_extension(key):
            raise ValidationError({"object_key": gettext("Photo object key is outside this space.")})
        if storage.public_image_key_in_use(space.makerspace_id, key):
            raise ValidationError({"object_key": gettext("This image is already in use.")})
        try:
            result = storage.finalize_upload(key)
            if result.status != "ok":
                services_gallery.cleanup_unattached(key)
                raise ValidationError({"object_key": storage.finalize_error_message(result)})
            if not storage.sniff_is_valid_image(key):
                services_gallery.cleanup_unattached(key)
                raise ValidationError({"object_key": gettext("Uploaded file is not a valid image.")})
        except StorageUnavailable:
            return storage_unavailable_response()
        try:
            photo = services_gallery.attach_photo(space, actor=request.user, object_key=key, size_bytes=result.size,
                                                  caption=body.validated_data["caption"])
        except Exception:
            services_gallery.cleanup_unattached(key)
            raise
        return Response(SpacePhotoSerializer(photo).data, status=status.HTTP_201_CREATED)


class SpacePhotoPresignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Create a place photo upload URL (staging key)",
                   request=SpaceImagePresignRequestSerializer,
                   responses={201: SpaceImagePresignResponseSerializer, **IMAGE_ERROR_RESPONSES})
    def post(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        body = SpaceImagePresignRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            key, upload = services_gallery.presign_photo(space, **body.validated_data)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(SpaceImagePresignResponseSerializer({"object_key": key, "upload": upload}).data,
                        status=status.HTTP_201_CREATED)


class SpacePhotoOrderView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Reorder a space's place photos",
                   request=SpacePhotoOrderSerializer,
                   responses={200: SpacePhotoListSerializer, **IMAGE_ERROR_RESPONSES})
    def put(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        body = SpacePhotoOrderSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        services_gallery.reorder_photos(space, actor=request.user, order=body.validated_data["order"])
        return _listing(request, space)


class SpacePhotoDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Edit a place photo caption",
                   request=SpacePhotoUpdateSerializer,
                   responses={200: SpacePhotoSerializer, **IMAGE_ERROR_RESPONSES})
    def patch(self, request, pk, photo_id):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        body = SpacePhotoUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        photo = services_gallery.update_photo(space, photo_id, actor=request.user,
                                              caption=body.validated_data["caption"])
        return Response(SpacePhotoSerializer(photo).data)

    @extend_schema(tags=["Admin bookings"], summary="Remove a place photo", request=None,
                   responses={204: None, **IMAGE_ERROR_RESPONSES})
    def delete(self, request, pk, photo_id):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        services_gallery.delete_photo(space, photo_id, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
