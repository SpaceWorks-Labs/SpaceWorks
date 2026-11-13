"""PATCH/DELETE for ticket types and event categories (refused when history depends on them)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from . import ticketing_edit
from .models import EventCategory, EventTicketType
from .serializers_speakers import CategoryPatchSerializer, TicketPatchSerializer
from .serializers_ticketing import CategorySerializer, TicketSerializer
from .views_admin_event_detail import _visible_makerspace
from .views_invites import ERRORS, manageable_event_code
from apps.payments.price_drop.preview import PREVIEW_PARAMETER, previewable

TAGS = ["Admin events"]
CONFLICT = {409: OpenApiResponse(ErrorSerializer, description="Referenced by registrations or events (code names which).")}


def _ticket(request, pk):
    # Occurrence ticket types only; series templates are edited with their series.
    return manageable_event_code(request.user, EventTicketType.objects.filter(event__isnull=False), pk)


def _category(request, makerspace_id, pk):
    space = _visible_makerspace(request.user, makerspace_id)
    rows = rbac.scope_by_action(request.user, rbac.Action.MANAGE_EVENTS, EventCategory.objects.all())
    return get_object_or_404(rows.filter(makerspace=space), pk=pk)


class EventTicketDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=TicketPatchSerializer, responses={200: TicketSerializer, **ERRORS, **CONFLICT},
                   parameters=[PREVIEW_PARAMETER],
                   description="Edit a ticket type. Price and audience are frozen once any registration used it "
                               "(409 ticket_type_referenced), except that with `charges.price_drop_refunds` on a "
                               "fixed price may be LOWERED, which opens a refund case per paid seat for an event not "
                               "yet held. Capacity cannot drop below live registrations. Audited.")
    @previewable
    def patch(self, request, pk):
        ticket = _ticket(request, pk)
        values = TicketPatchSerializer(data=request.data, partial=True)
        values.is_valid(raise_exception=True)
        row = ticketing_edit.update_ticket(ticket, actor=request.user, **values.validated_data)
        return Response(TicketSerializer(row).data)

    @extend_schema(tags=TAGS, request=None, responses={204: None, **ERRORS, **CONFLICT},
                   description="Delete an unused ticket type. A referenced one returns 409 ticket_type_referenced; "
                               "deactivate it instead. Audited.")
    def delete(self, request, pk):
        ticketing_edit.delete_ticket(_ticket(request, pk), actor=request.user)
        return Response(status=204)


class EventCategoryDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=CategoryPatchSerializer, responses={200: CategorySerializer, **ERRORS},
                   description="Rename a category or change its slug (unique per makerspace). Audited.")
    def patch(self, request, makerspace_id, pk):
        category = _category(request, makerspace_id, pk)
        values = CategoryPatchSerializer(data=request.data, partial=True)
        values.is_valid(raise_exception=True)
        row = ticketing_edit.update_category(category, actor=request.user, **values.validated_data)
        return Response(CategorySerializer(row).data)

    @extend_schema(tags=TAGS, request=None, responses={204: None, **ERRORS, **CONFLICT},
                   description="Delete an unused category. One that events use returns 409 category_referenced. Audited.")
    def delete(self, request, makerspace_id, pk):
        ticketing_edit.delete_category(_category(request, makerspace_id, pk), actor=request.user)
        return Response(status=204)
