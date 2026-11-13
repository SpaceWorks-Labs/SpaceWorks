from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.bookings.serializers_admin import (
    BookableSpaceAdminSerializer,
    BookableSpaceListResponseSerializer,
    BookableSpaceWriteSerializer,
    EmptyActionSerializer,
    SpaceImageFinalizeRequestSerializer,
    SpaceImagePresignRequestSerializer,
    SpaceImagePresignResponseSerializer,
)
from apps.bookings import services, services_images, storage
from apps.bookings.models import BookableSpace
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.hardware_requests.view_helpers import (
    ERROR_400,
    ERROR_401,
    ERROR_403,
    ERROR_404,
    ERROR_409,
    ERROR_503,
)
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace
from apps.payments.price_drop.preview import PREVIEW_PARAMETER, previewable


SCOPED_ERROR_RESPONSES = {400: ERROR_400, 401: ERROR_401, 403: ERROR_403, 404: ERROR_404}
VALIDATED_ERROR_RESPONSES = {400: ERROR_400, **SCOPED_ERROR_RESPONSES}
IMAGE_ERROR_RESPONSES = {**VALIDATED_ERROR_RESPONSES, 503: ERROR_503}


class _SpacePagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = 'page_size'
    max_page_size = 200


def _visible_makerspace(actor, makerspace_id, permission=None):
    from django.db.models import Q
    from .booking_authority import spaces_for, require_tenant
    visible = rbac.scope_by_visibility_or_action(
        actor, rbac.Action.MANAGE_BOOKINGS, Makerspace.objects.all(), field="id")
    granted = spaces_for(actor, "view").values("makerspace_id")
    makerspace = get_object_or_404(Makerspace.objects.filter(
        Q(pk__in=visible.values("pk")) | Q(pk__in=granted)), pk=makerspace_id)
    require_module(makerspace, "bookings")
    if permission != "view" or not spaces_for(actor, "view").filter(makerspace=makerspace).exists():
        require_tenant(actor, makerspace)
    return makerspace


def manageable_space(actor, pk, permission=None):
    from .booking_authority import get_space
    return get_space(actor, pk, permission)


def _page_response(paginator, page, serializer, actor=None):
    from .booking_authority_page import authority_for_page, features_for_page
    context = {
        "actor": actor,
        "booking_authority": authority_for_page(actor, page),
        "booking_features": features_for_page(page),
    }
    return Response(
        {
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': serializer(page, many=True, context=context).data,
        }
    )


def _require_active(space):
    if not space.is_active:
        raise ValidationError(
            {'space': gettext('Inactive spaces cannot have images changed.')}
        )




class BookableSpaceDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'],
        summary='Retrieve a bookable space',
        request=None,
        responses={200: BookableSpaceAdminSerializer, **SCOPED_ERROR_RESPONSES},
    )
    def get(self, request, pk, *args, **kwargs):
        return Response(
            BookableSpaceAdminSerializer(manageable_space(request.user, pk, "view"), context={"actor": request.user}).data
        )

    @extend_schema(
        tags=['Admin bookings'],
        summary='Update a bookable space',
        request=BookableSpaceWriteSerializer,
        parameters=[PREVIEW_PARAMETER],
        responses={
            200: BookableSpaceAdminSerializer,
            **VALIDATED_ERROR_RESPONSES,
            409: ERROR_409,
        },
    )
    @previewable
    def patch(self, request, pk, *args, **kwargs):
        space = manageable_space(request.user, pk, "edit_details")
        serializer = BookableSpaceWriteSerializer(
            space,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        space = services.update_space(
            space,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(BookableSpaceAdminSerializer(space, context={"actor": request.user}).data)


class BookableSpaceDeactivateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'],
        summary='Deactivate a bookable space',
        request=EmptyActionSerializer,
        responses={
            200: BookableSpaceAdminSerializer,
            **VALIDATED_ERROR_RESPONSES,
            409: ERROR_409,
        },
    )
    def post(self, request, pk, *args, **kwargs):
        space = manageable_space(request.user, pk)
        serializer = EmptyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        space = services.deactivate_space(space, actor=request.user)
        return Response(BookableSpaceAdminSerializer(space, context={"actor": request.user}).data)


class BookableSpaceImagePresignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'],
        summary='Create a space image upload URL',
        request=SpaceImagePresignRequestSerializer,
        responses={201: SpaceImagePresignResponseSerializer, **IMAGE_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        space = manageable_space(request.user, pk, "edit_details")
        _require_active(space)
        serializer = SpaceImagePresignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content_type = serializer.validated_data['content_type']
        ext = storage.ext_for(content_type, serializer.validated_data['filename'])
        object_key = storage.build_object_key(space.makerspace_id, space.pk, ext)
        from apps.makerspaces.limits import check_upload_headroom
        check_upload_headroom(space.makerspace)  # #234: refuse before the upload when storage is full
        try:
            upload = storage.presigned_upload(object_key, content_type)
        except StorageUnavailable:
            return storage_unavailable_response()
        data = {'object_key': object_key, 'upload': upload}
        return Response(
            SpaceImagePresignResponseSerializer(data).data,
            status=status.HTTP_201_CREATED,
        )


def _cleanup_new_upload(space, object_key):
    services_images.cleanup_unattached_space_image(
        space,
        object_key=object_key,
        storage=storage,
    )


class BookableSpaceImageFinalizeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'],
        summary='Finalize and attach a space image',
        request=SpaceImageFinalizeRequestSerializer,
        responses={200: BookableSpaceAdminSerializer, **IMAGE_ERROR_RESPONSES},
    )
    def post(self, request, pk, *args, **kwargs):
        space = manageable_space(request.user, pk, "edit_details")
        _require_active(space)
        serializer = SpaceImageFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        object_key = serializer.validated_data['object_key']
        services.validate_space_image_key(space, object_key)
        if storage.public_image_key_in_use(space.makerspace_id, object_key):
            raise ValidationError({'object_key': gettext('This image is already in use.')})
        try:
            result = storage.finalize_upload(object_key)
        except StorageUnavailable:
            _cleanup_new_upload(space, object_key)
            return storage_unavailable_response()
        if result.status != 'ok':
            _cleanup_new_upload(space, object_key)
            raise ValidationError(
                {'object_key': storage.finalize_error_message(result)}
            )
        try:
            valid_image = storage.sniff_is_valid_image(object_key)
        except StorageUnavailable:
            _cleanup_new_upload(space, object_key)
            return storage_unavailable_response()
        if not valid_image:
            _cleanup_new_upload(space, object_key)
            raise ValidationError({'object_key': gettext('Uploaded file is not a valid image.')})
        try:
            space = services.set_space_image(
                space,
                actor=request.user,
                object_key=object_key,
                size_bytes=result.size,
            )
        except Exception:
            _cleanup_new_upload(space, object_key)
            raise
        return Response(BookableSpaceAdminSerializer(space, context={"actor": request.user}).data)


class BookableSpaceImageDeleteView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'],
        summary='Delete a space image',
        request=None,
        responses={204: None, **IMAGE_ERROR_RESPONSES},
    )
    def delete(self, request, pk, *args, **kwargs):
        space = manageable_space(request.user, pk, "edit_details")
        services.remove_space_image(space, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
