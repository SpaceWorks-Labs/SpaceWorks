"""Event equipment desk (staff) and "your equipment" (member) read surfaces."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.serializers import AdminRequestSerializer
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset

from rest_framework.exceptions import PermissionDenied

from . import event_permissions
from .equipment_desk import member_equipment, staff_desk
from .equipment_window import planning_event, set_return_hours
from django.utils.translation import gettext

NOT_FOUND = OpenApiResponse(description="Event, module, feature or authority unavailable.")


class EquipmentDeskWarning(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    code = serializers.ChoiceField(choices=["units_under_repair", "reserved_units_unavailable", "insufficient_stock"],
                                   help_text="Advisory only; accept and issue still decide through the workflow.")
    count = serializers.IntegerField(help_text="Units under repair, reserved units missing from the shelf, "
                                               "or units requested by loans awaiting review.")


class EventEquipmentDeskSummary(serializers.Serializer):
    awaiting_review = serializers.IntegerField()
    equipment_warnings = EquipmentDeskWarning(many=True, help_text=(
        "Products of this event's ready or awaiting-review loans that are under repair or short today."))
    ready_to_issue = serializers.IntegerField()
    out = serializers.IntegerField()
    overdue = serializers.IntegerField()
    outstanding_units = serializers.IntegerField()
    closed_with_issue = serializers.IntegerField()
    event_ends_at = serializers.DateTimeField(allow_null=True)
    equipment_return_hours = serializers.IntegerField(allow_null=True, help_text=(
        "Event loans fall due this many hours after the event ends; null means at the event end."))


class EventEquipmentDeskSerializer(serializers.Serializer):
    summary = EventEquipmentDeskSummary()
    ready = AdminRequestSerializer(many=True)
    out = AdminRequestSerializer(many=True)
    closed = AdminRequestSerializer(many=True)


class EventReturnWindowInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not hasattr(data, "keys") or set(data.keys()) - set(self.fields):
            raise serializers.ValidationError(gettext("Unexpected fields."))
        return super().to_internal_value(data)

    equipment_return_hours = serializers.IntegerField(
        allow_null=True, min_value=0, max_value=720,
        help_text="Hours after the event ends that its loans fall due; null or 0 means at the event end.")


class EventEquipmentDeskView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={
        200: EventEquipmentDeskSerializer, 401: OpenApiResponse(description="Authentication required."),
        403: OpenApiResponse(description="Staff or origin authority required."), 404: NOT_FOUND,
    }, description="Event-linked reviewed loans for the event-day desk: accepted (ready to issue), "
                   "out (issued or partially returned, soonest due first) and recently closed. Requires "
                   "event view authority AND issue_request; issue/return use the normal request endpoints.")
    def get(self, request, makerspace_id, event_id):
        _event, groups, summary = staff_desk(request.user, makerspace_id, event_id)
        data = {"summary": EventEquipmentDeskSummary(summary).data}
        for key, rows in groups.items():
            data[key] = AdminRequestSerializer(rows, many=True, context={"request": request}).data
        return Response(data)

    @extend_schema(tags=["Admin events"], request=EventReturnWindowInput, auth=[{"jwtAuth": []}], responses={
        200: EventReturnWindowInput, 401: OpenApiResponse(description="Authentication required."),
        403: OpenApiResponse(description="Session staff authority required."), 404: NOT_FOUND,
    }, description="Sets the event's equipment return window (decision 221b). Applies to loans issued after "
                   "the change; loans already issued keep their stored due time. Needs event edit_details "
                   "authority. Audited as event.equipment_return_window_changed.")
    def patch(self, request, makerspace_id, event_id):
        if getattr(request, "api_client", None) or getattr(request, "person_credential", None):
            raise PermissionDenied(gettext("This endpoint requires a staff session."))
        body = EventReturnWindowInput(data=request.data)
        body.is_valid(raise_exception=True)
        hours = body.validated_data["equipment_return_hours"] or None
        event = planning_event(request.user, makerspace_id, event_id, event_permissions.EDIT_DETAILS)
        updated = set_return_hours(request.user, event, hours)
        return Response({"equipment_return_hours": updated.equipment_return_hours})


class MemberEventEquipmentItem(serializers.Serializer):
    product_name = serializers.CharField()
    requested_quantity = serializers.IntegerField()
    accepted_quantity = serializers.IntegerField()
    issued_quantity = serializers.IntegerField()
    returned_quantity = serializers.IntegerField()


class MemberEventEquipmentRequest(serializers.Serializer):
    public_token = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    return_due_at = serializers.DateTimeField(allow_null=True)
    overdue = serializers.BooleanField()
    items = MemberEventEquipmentItem(many=True)


class MemberEventEquipmentSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_ends_at = serializers.DateTimeField(allow_null=True)
    can_request = serializers.BooleanField()
    requests = MemberEventEquipmentRequest(many=True)


class MemberEventEquipmentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member events"], responses={
        200: MemberEventEquipmentSerializer, 401: OpenApiResponse(description="Authentication required."),
        404: NOT_FOUND,
    }, description="The caller's own equipment requests linked to the event of one of their own "
                   "registrations, with status and due-back time. Never shows other people's loans.")
    def get(self, request, makerspace_id, pk):
        makerspace = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        user = request.user
        if not (user.is_active and user.access_status == "active" and not getattr(user, "is_tenant_dump_stub", False)):
            raise NotFound()
        return Response(MemberEventEquipmentSerializer(member_equipment(user, makerspace, pk)).data)
