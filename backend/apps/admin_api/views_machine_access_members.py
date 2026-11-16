"""Member picker for machine access: active members of the space, names only, no contact data."""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.pii_presentation import MASK, pii_visible
from apps.accounts.staff_identity import person_q
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_machine_access import _space
from apps.makerspaces.models import MakerspaceMembership
from apps.openapi_errors import errors


class MachineAccessCandidateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()


class MachineAccessCandidatesSerializer(serializers.Serializer):
    results = MachineAccessCandidateSerializer(many=True)


class MachineAccessCandidatesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machines"], summary="Find active members to give machine access",
                   parameters=[OpenApiParameter("q", str, OpenApiParameter.QUERY, description="Name search.")],
                   request=None, responses={200: MachineAccessCandidatesSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        rows = MakerspaceMembership.objects.select_related("user").filter(
            person_q("user__"), makerspace=space, status="active", user__is_active=True, user__access_status="active")
        term = request.query_params.get("q", "").strip()[:80]
        if term:
            rows = rows.filter(Q(user__display_name__icontains=term) | Q(user__username__icontains=term))
        rows = rows.order_by("user__display_name", "user__username", "pk")[:25]
        visible = pii_visible(request.user, space.pk)  # a platform account sees names only inside a PII window
        return Response({"results": [{"user_id": m.user_id, "name": (m.user.display_name or m.user.get_full_name()
                                      or m.user.username) if visible else MASK} for m in rows]})
