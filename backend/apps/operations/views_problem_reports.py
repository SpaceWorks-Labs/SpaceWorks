from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.audit import services as audit
from apps.hardware_requests.models import PublicProblemReport
from apps.hardware_requests.problem_report_workflow import triage_problem_report
from apps.operations.accountability import open_problem_reports
from apps.makerspaces.guards import require_module
from apps.openapi_errors import errors
from apps.operations.serializers_problem_reports import (
    ProblemReportQueueSerializer,
    ProblemReportResolvedSerializer,
    ProblemReportTriageResponseSerializer,
    ProblemReportTriageSerializer,
)
from apps.operations.views_reports import _makerspace_for_inventory_view


class ProblemReportListView(APIView):
    """Open problem reports, readable by whoever may triage them (EDIT_INVENTORY).

    Decision 224(a) moved the accountability page to the people area (MANAGE_MEMBERS), which
    left the Inventory Manager able to triage a report but with nowhere to list them.
    """

    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Analytics"],
        summary="List open public problem reports",
        request=None,
        responses={200: ProblemReportQueueSerializer, **errors(401, 403, 404)},
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = _makerspace_for_inventory_view(request.user, makerspace_id)
        require_action(request.user, rbac.Action.EDIT_INVENTORY, makerspace.id)
        require_module(makerspace, "reports")
        rows, truncated = open_problem_reports(makerspace.id)
        return Response({"results": rows, "truncated": truncated})


class ProblemReportResolveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Analytics"],
        summary="Resolve a public problem report",
        request=None,
        responses={200: ProblemReportResolvedSerializer, **errors(400, 401, 403, 404)},
    )
    def post(self, request, makerspace_id, pk, *args, **kwargs):
        makerspace = _makerspace_for_inventory_view(request.user, makerspace_id)
        require_action(request.user, rbac.Action.EDIT_INVENTORY, makerspace.id)
        require_module(makerspace, "reports")
        report = get_object_or_404(
            PublicProblemReport.objects.filter(makerspace_id=makerspace.id), pk=pk
        )
        if report.resolved_at is None:
            report.resolved_at = timezone.now()
            report.resolved_by = request.user
            report.save(update_fields=["resolved_at", "resolved_by"])
            audit.record(
                request.user,
                "public_problem.resolved",
                makerspace=makerspace,
                target=report,
                meta={"loan_id": report.loan_id},
            )
        return Response({"id": report.id, "resolved": True})


class ProblemReportTriageView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = ProblemReportTriageSerializer

    @extend_schema(
        tags=["Analytics"],
        summary="Triage a public problem report",
        request=ProblemReportTriageSerializer,
        responses={200: ProblemReportTriageResponseSerializer},
    )
    def post(self, request, makerspace_id, pk, *args, **kwargs):
        makerspace = _makerspace_for_inventory_view(request.user, makerspace_id)
        require_action(request.user, rbac.Action.EDIT_INVENTORY, makerspace.id)
        require_module(makerspace, "reports")
        report = get_object_or_404(
            PublicProblemReport.objects.filter(makerspace_id=makerspace.id), pk=pk
        )
        serializer = ProblemReportTriageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resolved = triage_problem_report(
            report, request.user, **serializer.validated_data
        )
        return Response(
            {
                "id": resolved.id,
                "outcome": resolved.outcome,
                "resolved": resolved.resolved_at is not None,
            }
        )