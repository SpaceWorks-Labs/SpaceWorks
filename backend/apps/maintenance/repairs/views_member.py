"""Members report a problem with what they used, and see their own reports (#103).

A member reports from their own loan, booking, machine job or machine session; anything else answers
`reporter_not_eligible`. Claim sessions (kiosk walk-in claims) never report. Members
never see staff notes, technicians, quotes or who works the job -- only the state.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.machines.views_service_cancel import _require_owner_session
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset

from . import areas, photos, reporting, services_issues as svc
from .serializers_actions import IssuePhotoUploadResponseSerializer, IssuePhotoUploadSerializer, IssueReportCreateSerializer
from .serializers_issues import IssueReportCreatedSerializer, MemberIssueReportSerializer
from .views_common import ERRORS

TAGS = ["Member repairs"]


class MemberIssuePhotoSerializer(IssuePhotoUploadSerializer):
    makerspace_id = serializers.IntegerField(min_value=1, required=False)
    makerspace_slug = serializers.SlugField(required=False)

    def validate(self, attrs):
        if not (attrs.get("makerspace_id") or attrs.get("makerspace_slug")):
            raise serializers.ValidationError({"makerspace_id": gettext("Name the makerspace.")})
        return attrs


def _space(pk=None, slug=None):
    lookup = {"pk": pk} if pk else {"slug": slug}
    space = get_object_or_404(servable_queryset(Makerspace.objects.all()), **lookup)
    if not areas.areas_on(space, areas.REPORTING):
        areas.refuse("issue reporting")
    return space


def report_subject(space, data, *, member=None, email_key=None, email=None):
    if data.get("loan_id"):
        origin, subject_type, subject = reporting.loan_subject(
            space, data["loan_id"], member=member, email_key=email_key, product_id=data.get("product_id"),
            asset_id=data.get("asset_id"))
        return "loan", origin, subject_type, subject
    if data.get("booking_id") or data.get("booking_token"):
        origin, subject_type, subject = reporting.booking_subject(
            space, data.get("booking_id"), token=data.get("booking_token"), member=member, email=email)
        return "booking", origin, subject_type, subject
    if data.get("machine_session_id"):
        origin, subject_type, subject = reporting.session_subject(space, data["machine_session_id"], member=member)
        return "session", origin, subject_type, subject
    origin, subject_type, subject = reporting.job_subject(space, data["machine_job_id"], member=member)
    return "machine_job", origin, subject_type, subject


class MemberIssueListView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(tags=TAGS, summary="Problems I reported", parameters=[OpenApiParameter("makerspace", int, required=False)],
                   responses={200: MemberIssueReportSerializer(many=True), **ERRORS})
    def get(self, request):
        from apps.maintenance.models import IssueReport
        user = _require_owner_session(request)
        rows = servable_queryset(IssueReport.objects.filter(reporter=user).select_related(
            "makerspace", "machine", "product", "asset", "room"), relation="makerspace")
        if (space := request.query_params.get("makerspace")) and str(space).isdigit():
            rows = rows.filter(makerspace_id=int(space))
        return Response(MemberIssueReportSerializer(rows.order_by("-created_at")[:100], many=True).data)

    @extend_schema(tags=TAGS, summary="Report a problem with my loan, booking, machine job or machine session",
                   request=IssueReportCreateSerializer, responses={201: IssueReportCreatedSerializer, **ERRORS})
    def post(self, request):
        user = _require_owner_session(request)
        body = IssueReportCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if not (data.get("makerspace_id") or data.get("makerspace_slug")):
            raise serializers.ValidationError({"makerspace_id": gettext("Name the makerspace.")})
        space = _space(data.get("makerspace_id"), data.get("makerspace_slug"))
        source, origin, subject_type, subject = report_subject(space, data, member=user)
        validated = photos.validate(space, data["photos"], photos.owner_for_user(user))
        issue = svc.file_report(space, reporter=user, source=source, origin=origin, subject_type=subject_type,
                                subject=subject, title=data["title"], description=data["description"],
                                validated=validated, reporter_name=user.display_name or user.get_full_name(),
                                reporter_email="")
        return Response({"id": issue.pk, "state": issue.state}, status=status.HTTP_201_CREATED)


class MemberIssuePhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(tags=TAGS, summary="Presign a private photo for my report (staging key)",
                   request=MemberIssuePhotoSerializer, responses={201: IssuePhotoUploadResponseSerializer, **ERRORS})
    def post(self, request):
        user = _require_owner_session(request)
        body = MemberIssuePhotoSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        space = _space(body.validated_data.get("makerspace_id"), body.validated_data.get("makerspace_slug"))
        try:
            data = photos.issue_upload(space, body.validated_data["content_type"], photos.owner_for_user(user))
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(data, status=status.HTTP_201_CREATED)


class LoanItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    asset_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()


class MemberLoanItemsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "request_status"

    @extend_schema(tags=TAGS, summary="What I can report on from one of my loans",
                   parameters=[OpenApiParameter("makerspace", int), OpenApiParameter("loan", int)],
                   responses={200: LoanItemSerializer(many=True), **ERRORS})
    def get(self, request):
        from apps.hardware_requests.models import HardwareRequestItemAsset
        user = _require_owner_session(request)
        space_id, loan_id = request.query_params.get("makerspace", ""), request.query_params.get("loan", "")
        if not (space_id.isdigit() and loan_id.isdigit()):
            raise serializers.ValidationError({"loan": gettext("Give the makerspace and the loan.")})
        loan = reporting._loan(_space(int(space_id)), int(loan_id), user, None)
        units = HardwareRequestItemAsset.objects.filter(request_item__request=loan).select_related("asset__product")
        rows = [{"product_id": unit.asset.product_id, "asset_id": unit.asset_id,
                 "name": f"{unit.asset.product.name} ({unit.asset.asset_tag})"} for unit in units]
        with_units = {row["product_id"] for row in rows}
        rows += [{"product_id": item.product_id, "asset_id": None, "name": item.product.name}
                 for item in loan.items.select_related("product") if item.product_id not in with_units]
        return Response(rows)
