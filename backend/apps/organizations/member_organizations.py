"""Own organization membership discovery, independent of tenant staff access."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.admin_api.permissions import active_user
from .models import Organization
from .member_leave import LeaveError, LeaveStateSerializer, project_leave_state


class OwnOrganizationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    leave_state = LeaveStateSerializer()


class OwnOrganizationsPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = OwnOrganizationSerializer(many=True)


class MemberOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member organizations"], request=None,
                   responses={200: OwnOrganizationsPageSerializer,
                              **{code: LeaveError for code in (401, 403, 429)}})
    def get(self, request):
        actor = request.user
        if not active_user(actor) or actor.account_kind != "member":
            raise PermissionDenied()
        rows = Organization.objects.filter(memberships__user=actor).order_by("name", "pk").distinct()
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response([
            {"id": row.pk, "name": row.name, "slug": row.slug,
             "leave_state": project_leave_state(row, actor)} for row in page
        ])
        response["Cache-Control"] = "private, no-store"
        return response
