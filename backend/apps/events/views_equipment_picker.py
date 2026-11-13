from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority, event_permissions
from apps.events.models import Event
from apps.inventory.equipment_picker import RequestableProductPage, product_page
from apps.inventory.equipment_public_kits import PublicKitPage, kit_page
from apps.makerspaces.guards import require_feature, require_module


class EventEquipmentProductsView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(
        parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number.")],
        responses={200: RequestableProductPage, 401: OpenApiResponse(description="Authentication required."),
                   403: OpenApiResponse(description="Staff or origin authority required."),
                   404: OpenApiResponse(description="Target, module, feature or page unavailable.")},
    )
    def get(self, request, makerspace_id, event_id):
        event = get_object_or_404(Event.objects.select_related("makerspace"),
                                  pk=event_id, makerspace_id=makerspace_id)
        require_module(event.makerspace, "events")  # switches answer before the authority check
        require_module(event.makerspace, "request_workflow")
        if (event.status in {Event.Status.CANCELLED, Event.Status.COMPLETED}
                or not event_authority.can(request.user, event, event_permissions.MANAGE_REGISTRATIONS)):
            raise NotFound()
        require_feature(event.makerspace, "loans.enabled")
        # Organizers who may also view inventory see the availability owner's stored count.
        return product_page(request, event.makerspace, availability=rbac.can(
            request.user, rbac.Action.VIEW_INVENTORY, event.makerspace_id), event_context=True)


class EventEquipmentKitsView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(
        parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY, description="One-based page number.")],
        responses={200: PublicKitPage, 401: OpenApiResponse(description="Authentication required."),
                   403: OpenApiResponse(description="Staff or origin authority required."),
                   404: OpenApiResponse(description="Target, module, feature or page unavailable.")},
    )
    def get(self, request, makerspace_id, event_id):
        event = get_object_or_404(Event.objects.select_related("makerspace"),
                                  pk=event_id, makerspace_id=makerspace_id)
        require_module(event.makerspace, "events")
        if (event.status in {Event.Status.CANCELLED, Event.Status.COMPLETED}
                or not event_authority.can(request.user, event, event_permissions.MANAGE_REGISTRATIONS)):
            raise NotFound()
        return kit_page(request, event.makerspace)
