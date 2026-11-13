"""Who may be assigned a follow-up on an incident (0.12.0, UI lane U2; decision 219 (e)).

Candidates are the space's active staff who could themselves triage this incident: the same
`scope.can_triage` test that narrows the register to an area, so a Machine Manager is offered
only for a machine incident they reach, and an `other`-area incident offers Space Managers alone.
Only people who may triage the incident can ask, and only `{id, display_name}` leaves.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.accounts.membership_context import valid_staff_membership_q
from apps.makerspaces.models import MakerspaceMembership
from apps.openapi_errors import errors

from . import scope
from .views import STAFF_TAGS, _staff_incident


class AssigneeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class AssigneeListSerializer(serializers.Serializer):
    results = AssigneeSerializer(many=True)


class IncidentAssigneeListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, summary="Staff who may be assigned a follow-up on this incident", request=None,
                   responses={200: AssigneeListSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        incident = _staff_incident(request.user, pk)
        rows = (MakerspaceMembership.staff_tracks.filter(valid_staff_membership_q(), makerspace=incident.makerspace,
                                                         status="active").select_related("user")
                .order_by("user__display_name", "user_id"))
        seen, results = set(), []
        for row in rows:
            user = row.user
            if user.pk in seen or not user.is_active or not scope.can_triage(user, incident):
                continue
            seen.add(user.pk)
            results.append({"id": user.pk, "display_name": user.display_name or user.get_full_name() or user.username})
        return Response({"results": results})
