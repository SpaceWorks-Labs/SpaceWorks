from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.bookings import booking_authority, booking_permissions
from apps.bookings.models import BookableSpace
from apps.inventory.equipment_picker import RequestableProductPage, product_page
from apps.inventory.equipment_public_kits import PublicKitPage, kit_page
from apps.makerspaces.guards import require_feature, require_module


class BookingEquipmentProductsView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(
        parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number.")],
        responses={200: RequestableProductPage, 401: OpenApiResponse(description="Authentication required."),
                   403: OpenApiResponse(description="Staff or origin authority required."),
                   404: OpenApiResponse(description="Target, module, feature or page unavailable.")},
    )
    def get(self, request, makerspace_id, space_id):
        space = get_object_or_404(BookableSpace.objects.select_related("makerspace"),
                                  pk=space_id, makerspace_id=makerspace_id)
        if not space.is_active or not booking_authority.can(request.user, space, booking_permissions.MANAGE_RESERVATIONS):
            raise NotFound()
        require_module(space.makerspace, "bookings")
        require_module(space.makerspace, "request_workflow")
        require_feature(space.makerspace, "loans.enabled")
        return product_page(request, space.makerspace)


class BookingEquipmentKitsView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(
        parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number.")],
        responses={200: PublicKitPage, 401: OpenApiResponse(description="Authentication required."),
                   403: OpenApiResponse(description="Staff or origin authority required."),
                   404: OpenApiResponse(description="Target, module, feature or page unavailable.")},
    )
    def get(self, request, makerspace_id, space_id):
        space = get_object_or_404(BookableSpace.objects.select_related("makerspace"),
                                  pk=space_id, makerspace_id=makerspace_id)
        if not space.is_active or not booking_authority.can(request.user, space, booking_permissions.MANAGE_RESERVATIONS):
            raise NotFound()
        require_module(space.makerspace, "bookings")
        return kit_page(request, space.makerspace)
