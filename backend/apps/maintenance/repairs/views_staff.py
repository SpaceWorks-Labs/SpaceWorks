"""Staff routes around the queue: photo presigns, a Technician's "My jobs" and service state."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable

from . import areas, authority, photos, service_state
from .serializers_actions import IssuePhotoUploadResponseSerializer, IssuePhotoUploadSerializer, ServiceStateChangeSerializer
from .serializers_issues import IssueReportListSerializer
from .views_common import ERRORS, TAGS, IssuePagination, issue_rows, require_issues, space_for


def works_here(actor, space):
    return areas.manages_any(actor, space.pk) or rbac.can(actor, rbac.Action.WORK_REPAIRS, space.pk)


class IssuePhotoUploadView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Presign a private photo for a repair step (staging key)",
                   request=IssuePhotoUploadSerializer, responses={201: IssuePhotoUploadResponseSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        require_issues(space)
        if not works_here(request.user, space):
            raise PermissionDenied()
        body = IssuePhotoUploadSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            data = photos.issue_upload(space, body.validated_data["content_type"], photos.owner_for_user(request.user))
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(data, status=201)


class MyRepairJobsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="My jobs: open repairs assigned to me (24 per page)",
                   responses={200: IssueReportListSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        require_issues(space)
        mine = authority.visible_issues(request.user, space).filter(authority.assigned_q(request.user))
        if request.query_params.get("state") != "all":
            from apps.maintenance.models import IssueReport
            mine = mine.filter(state__in=IssueReport.OPEN_STATES)
        rows = issue_rows().filter(pk__in=mine.values("pk")).order_by("-created_at", "-id")
        paginator = IssuePagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(
            IssueReportListSerializer(page, many=True, context={"request": request, "actor": request.user}).data)


class AffectedBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()


class ServiceStateResultSerializer(serializers.Serializer):
    state = serializers.CharField()
    outage_id = serializers.IntegerField(allow_null=True)
    affected_bookings = AffectedBookingSerializer(many=True)


class ServiceStateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Take a machine, item, unit or room in or out of service",
                   request=ServiceStateChangeSerializer, responses={200: ServiceStateResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        body = ServiceStateChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        subject = get_object_or_404(areas.subject_model(data["subject_type"]).objects.filter(makerspace=space),
                                    pk=data.pop("subject_id"))
        issue = None
        if issue_id := data.pop("issue_id"):
            issue = get_object_or_404(issue_rows().filter(makerspace=space), pk=issue_id)
        result = service_state.set_state(request.user, space, subject=subject, issue=issue, **data)
        # Affected bookings are listed only to staff who decide on them (booking authority).
        bookings = result["bookings"] if rbac.can(request.user, rbac.Action.MANAGE_BOOKINGS, space.pk) else []
        return Response({"state": result["state"], "outage_id": getattr(result["outage"], "pk", None),
                         "affected_bookings": [{"id": row.pk, "starts_at": row.starts_at, "ends_at": row.ends_at,
                                                "status": row.status} for row in bookings]})
