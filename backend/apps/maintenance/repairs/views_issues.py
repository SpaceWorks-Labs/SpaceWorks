"""Staff issue routes: the queue, opening a job, the detail page, and each lifecycle step.

Every step route has the same shape -- look the issue up through rbac scope and the
actor's visibility, validate one body, call one service, answer the refreshed detail --
so `step_view` builds them from (body serializer, summary, service call) instead of a
dozen copies of the same view. Authorization is never here: each service re-checks who
may do that step (manager in their area, or the assigned Technician).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from . import areas, authority, dispatch as dispatching, photos, services_issues as svc, services_work as work
from .serializers_actions import (
    IssueAssignSerializer, IssueDispatchRequestSerializer, IssueNoteSerializer, IssueOpenSerializer,
    IssueRejectSerializer, IssueTriageSerializer, IssueUnassignSerializer, RepairFixSerializer,
    RepairPartWriteSerializer, RepairPayoutSerializer, RepairQuoteDecisionSerializer, RepairQuoteSerializer,
    RepairWorkLogSerializer,
)
from .serializers_issues import IssueReportDetailSerializer, IssueReportListSerializer
from .views_common import ERRORS, TAGS, IssuePagination, detail, issue_for, issue_rows, require_issues, space_for


class IssueListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Issues and repair jobs in my scope (24 per page)",
                   parameters=[OpenApiParameter("state", str, required=False),
                               OpenApiParameter("area", str, required=False),
                               OpenApiParameter("assigned", str, required=False, enum=["me"])],
                   responses={200: IssueReportListSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        require_issues(space)
        rows = authority.visible_issues(request.user, space)
        if value := request.query_params.get("state"):
            rows = rows.filter(state__in=value.split(","))
        if (value := request.query_params.get("area")) in areas.AREAS:
            rows = rows.filter(area=value)
        if request.query_params.get("assigned") == "me":
            rows = rows.filter(authority.assigned_q(request.user))
        rows = issue_rows().filter(pk__in=rows.values("pk")).order_by("-created_at", "-id")
        paginator = IssuePagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(
            IssueReportListSerializer(page, many=True, context={"request": request, "actor": request.user}).data)

    @extend_schema(tags=TAGS, summary="Open a repair job (staff, no reporter)", request=IssueOpenSerializer,
                   responses={201: IssueReportDetailSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        body = IssueOpenSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        subject = get_object_or_404(areas.subject_model(data["subject_type"]).objects.filter(makerspace=space),
                                    pk=data.pop("subject_id"))
        issue = svc.open_issue(request.user, space, subject=subject, **data)
        return Response(detail(request, issue), status=status.HTTP_201_CREATED)


class IssueDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="One issue with its full history",
                   responses={200: IssueReportDetailSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(detail(request, issue_for(request.user, pk)))


class _StepView(APIView):
    permission_classes = [IsActiveStaff]
    body = None

    def post(self, request, pk):
        issue = issue_for(request.user, pk)
        data = {}
        if self.body is not None:
            serializer = self.body(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = dict(serializer.validated_data)
        type(self).act(request, issue, data)
        return Response(detail(request, issue))


def step_view(name, body, summary, act):
    view = type(name, (_StepView,), {"body": body, "act": staticmethod(act)})
    return extend_schema_view(post=extend_schema(
        tags=TAGS, summary=summary, request=body, responses={200: IssueReportDetailSerializer, **ERRORS}))(view)


def _owner(request):
    return photos.owner_for_user(request.user)


IssueTriageView = step_view("IssueTriageView", IssueTriageSerializer, "Triage a reported issue",
                            lambda r, i, d: svc.triage(r.user, i, priority=d.get("priority"), note=d["note"]))
IssueRejectView = step_view("IssueRejectView", IssueRejectSerializer, "Reject an issue with a reason",
                            lambda r, i, d: svc.reject(r.user, i, reason=d["reason"]))
IssueCloseView = step_view("IssueCloseView", IssueNoteSerializer, "Close a fixed issue",
                           lambda r, i, d: svc.close(r.user, i, note=d["note"]))
IssueStartView = step_view("IssueStartView", None, "Start the repair work",
                           lambda r, i, d: svc.start(r.user, i))
IssueUnassignView = step_view("IssueUnassignView", IssueUnassignSerializer, "Remove an assignee",
                              lambda r, i, d: svc.unassign(r.user, i, d["assignment_id"]))
IssueFixView = step_view("IssueFixView", RepairFixSerializer, "Mark the issue fixed (the reporter is told)",
                         lambda r, i, d: svc.fix(r.user, i, resolution=d["resolution"], photo_tokens=d["photos"],
                                                 owner=_owner(r)))
IssueWorkLogView = step_view(
    "IssueWorkLogView", RepairWorkLogSerializer, "Log a visit or a remark, with photos",
    lambda r, i, d: work.log_work(r.user, i, kind=d["kind"], note=d["note"], occurred_on=d["occurred_on"],
                                  contact_id=d["contact_id"], photo_tokens=d["photos"], owner=_owner(r)))
IssuePartsView = step_view("IssuePartsView", RepairPartWriteSerializer, "Record a part used or needed",
                           lambda r, i, d: work.record_part(r.user, i, **d))
IssueQuoteView = step_view("IssueQuoteView", RepairQuoteSerializer, "Record a technician's quote",
                           lambda r, i, d: work.quote(r.user, i, **d))
IssueApproveView = step_view("IssueApproveView", RepairQuoteDecisionSerializer, "Approve or decline the quote",
                             lambda r, i, d: work.decide_quote(r.user, i, approve=d["approve"], note=d["note"]))
IssuePayoutView = step_view("IssuePayoutView", RepairPayoutSerializer,
                            "Record the technician's payout in the finance ledger",
                            lambda r, i, d: work.record_payout(r.user, i, **d))
IssueDispatchView = step_view(
    "IssueDispatchView", IssueDispatchRequestSerializer, "Send the issue to technicians (email and chat)",
    lambda r, i, d: dispatching.dispatch(r.user, i, contact_ids=d["contact_ids"], channel_names=d["channels"],
                                         note=d["note"]))


def _assign(request, issue, data):
    contact = None
    if data["contact_id"] is not None:
        from apps.maintenance.models import TechnicianContact
        contact = TechnicianContact.objects.filter(makerspace_id=issue.makerspace_id, pk=data["contact_id"]).first()
        if contact is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"contact_id": "Choose a technician of this makerspace."})
    svc.assign(request.user, issue, contact=contact, myself=data["myself"])


IssueAssignView = step_view("IssueAssignView", IssueAssignSerializer, "Assign a technician, or yourself",
                            _assign)
