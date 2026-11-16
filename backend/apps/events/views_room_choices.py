"""Organizer-facing room choices for the event-creation room step (release 0.12.0, UI lane U2).

An organizer holding `manage_events` but no booking role cannot read `admin/.../spaces/`, and public
spaces carry only a `public_token`. This read-only list returns just what the room step needs — id, name,
capacity, whether the room needs approval and an availability-style status — and never a booker identity.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.bookings.models import BookableSpace
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module

from .views_admin_event_detail import _visible_makerspace


class RoomChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    capacity = serializers.IntegerField()
    needs_approval = serializers.BooleanField()
    status = serializers.ChoiceField(choices=["available", "approval_required"], help_text=(
        "`available` books instantly; `approval_required` is requested and held until staff decide."))


class RoomChoiceListSerializer(serializers.Serializer):
    results = RoomChoiceSerializer(many=True)


class EventRoomChoicesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin events"], summary="List rooms an organizer may choose in the event room step",
        request=None,
        responses={200: RoomChoiceListSerializer, **{code: ErrorSerializer for code in (401, 403, 404)}},
    )
    def get(self, request, makerspace_id):
        makerspace = _visible_makerspace(request.user, makerspace_id)
        require_module(makerspace, "bookings")
        rows = (BookableSpace.objects.filter(makerspace=makerspace, is_active=True)
                .exclude(kind=BookableSpace.Kind.MACHINE).order_by("name", "id"))
        needs = BookableSpace.ApprovalMode.APPROVE
        results = [{
            "id": row.pk, "name": row.name, "capacity": row.capacity,
            "needs_approval": row.approval_mode == needs,
            "status": "approval_required" if row.approval_mode == needs else "available",
        } for row in rows]
        return Response({"results": results})
