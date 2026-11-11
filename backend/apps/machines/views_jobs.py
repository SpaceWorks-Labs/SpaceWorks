"""The uniform "Request a job" routes (#140/#141): types, uploads, submit, and my jobs."""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle, MemberPrincipalRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines import job_intake, job_policy
from apps.machines.job_files import stage_job_file
from apps.machines.models import MachineServiceRequest
from apps.machines.serializers_jobs import (
    JobSubmitSerializer, JobTypeSerializer, JobUploadSerializer, MemberJobSerializer,
)
from apps.machines.views_service_cancel import _owned, _require_owner_session
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.servability import servable_queryset

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404, 409, 429)}


class JobCreatedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    public_token = serializers.UUIDField()
    status = serializers.CharField()


class JobUploadResponseSerializer(serializers.Serializer):
    file_id = serializers.IntegerField()
    upload = serializers.DictField()
    group = serializers.CharField()
    max_bytes = serializers.IntegerField()
    preview = serializers.CharField()


def _space(slug):
    space = get_public_makerspace(slug)
    require_module_for_servable(space, "machine_service")
    from apps.machines.public_intake_access import require_public_intake_available
    require_public_intake_available(space)  # `machines.job_requests` first, then membership + presence
    return space


def _type_row(space, queue):
    from apps.maker_formats.registry import REGISTRY
    from apps.machines.printer_capabilities import is_printer_type
    policy = job_policy.policy_for(space, queue.machine_type)
    groups = list(job_policy.file_groups(space, queue.machine_type))
    return {"queue_id": queue.pk, "name": queue.name, "machine_type_id": queue.machine_type_id,
            "machine_type_name": queue.machine_type.name, "machine_type_slug": queue.machine_type.slug,
            "is_printer": is_printer_type(queue.machine_type), "file_groups": groups,
            "accepted_extensions": sorted({spec.extension for spec in REGISTRY.values() if spec.group in groups}),
            "quotes": policy.quote_mode if job_policy.feature_enabled(space, job_policy.JOB_QUOTES)
            and job_policy.charges_tracked(space) else "off",
            "prepay": job_policy.prepay(space, queue.machine_type),
            "runs_unattended": job_policy.runs_unattended(space, queue.machine_type, policy),
            "max_open_jobs": policy.max_open_jobs}


class PublicJobTypesView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public machine service"], auth=[], summary="Machine types taking job requests",
                   responses={200: JobTypeSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_slug):
        space = _space(makerspace_slug)
        return Response(JobTypeSerializer([_type_row(space, row) for row in job_intake.job_queues(space)],
                                          many=True).data)


class PublicJobUploadView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "print_request_submit"

    @extend_schema(tags=["Public machine service"], summary="Stage a job file (checked against the type's formats)",
                   request=JobUploadSerializer, responses={201: JobUploadResponseSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = _space(makerspace_slug)
        payload = JobUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        queue = job_intake.resolve_queue(space, data["queue_id"])
        job_intake.require_member_job_gate(space, request.user, queue.machine_type)
        upload, presigned, accepts = stage_job_file(queue, request.user, filename=data["filename"],
                                                    content_type=data["content_type"], kind=data["kind"])
        return Response({"file_id": upload.pk, "upload": presigned, **accepts}, status=status.HTTP_201_CREATED)


class PublicJobSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(tags=["Public machine service"], summary="Request a job on any machine type",
                   description=("Members of this makerspace who are checked in (and have signed the waiver when "
                                "waivers are on). Files must be staged first. The 3D-printer form is an alias."),
                   request=JobSubmitSerializer, responses={201: JobCreatedSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = _space(makerspace_slug)
        payload = JobSubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = job_intake.submit_job(space, request.user, payload.validated_data)
        return Response(JobCreatedSerializer(row).data, status=status.HTTP_201_CREATED)


def _member_rows(user):
    return servable_queryset(MachineServiceRequest.objects.select_related(
        "makerspace", "queue__machine_type", "bucket__machine__machine_type").filter(member_id=user.pk),
        relation="makerspace")


def _render(rows, user, many=False):
    from apps.machines.service_queue_eta import queue_snapshot_for
    rows = list(rows) if many else [rows]
    context = {"queue_snapshot": queue_snapshot_for(rows), "user": user, "service_on": {}}
    data = MemberJobSerializer(rows, many=True, context=context).data
    return data if many else data[0]


class MemberJobListView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "request_status"

    @extend_schema(tags=["Member machine service"], summary="My machine jobs",
                   parameters=[OpenApiParameter("makerspace", int, required=False)],
                   responses={200: MemberJobSerializer(many=True), **ERRORS})
    def get(self, request):
        user = _require_owner_session(request)
        rows = _member_rows(user)
        if (space := request.query_params.get("makerspace")) and str(space).isdigit():
            rows = rows.filter(makerspace_id=int(space))
        return Response(_render(rows.order_by("-created_at")[:100], user, many=True))


class MemberJobDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "request_status"

    @extend_schema(tags=["Member machine service"], summary="One of my machine jobs, with its timeline",
                   responses={200: MemberJobSerializer, **ERRORS})
    def get(self, request, pk):
        user = _require_owner_session(request)
        response = Response(_render(_owned(user, Q(pk=pk)), user))
        response["Cache-Control"] = "no-store"
        return response
