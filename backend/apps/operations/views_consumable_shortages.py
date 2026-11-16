"""Staff read: upcoming events/bookings short of planned consumables (open item C25)."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace
from .consumable_shortages import WINDOW_DAYS, planned_shortages

ERRORS = {code: ErrorSerializer for code in (401, 403, 404)}


class PlannedShortageSerializer(serializers.Serializer):
    subject_kind = serializers.ChoiceField(choices=["event", "booking"])
    subject_id = serializers.IntegerField()
    subject_title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    remaining_planned = serializers.IntegerField()
    available_quantity = serializers.IntegerField()
    shortage_quantity = serializers.IntegerField()
    replenishment_quantity = serializers.IntegerField()


class PlannedShortageListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin inventory"], summary="Upcoming events and bookings short of planned consumables",
        description=(f"Next {WINDOW_DAYS} days. Requires view_inventory and the consumables feature; each "
                     "activity is re-checked with the event or booking view permission and skipped when refused. "
                     "Only rows with a shortage or a reorder suggestion are returned."),
        responses={200: PlannedShortageSerializer(many=True), **ERRORS},
    )
    def get(self, request, makerspace_id):
        space = get_object_or_404(
            rbac.scope_by_makerspace(request.user, Makerspace.objects.all(), makerspace_field="id"), pk=makerspace_id)
        require_module(space, "staff_admin")
        rows = planned_shortages(request.user, space)
        return Response(PlannedShortageSerializer(rows, many=True).data)
