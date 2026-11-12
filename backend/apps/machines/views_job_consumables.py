"""A job's profile consumables (decision 341): staff read and record; members self-report their own.

Staff go through the machine-service manage resolver (MANAGE_MACHINES plus machine scope), so a
Machine Manager reaches only jobs in their area. A member may report an actual only on their own
job, only for consumables the type lets members report, and only while the job is accepted,
running or done -- never before staff took it on.
"""

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import MemberPrincipalRateThrottle

from . import consumable_usage as usage
from .models import MachineServiceRequest
from .serializers_consumable_profiles import (
    ConsumableEntrySerializer, JobConsumablesSerializer, RecordConsumablesSerializer, JobConsumableUsageSerializer,
)
from .views_consumable_profiles import ERRORS

MEMBER_STATUSES = (MachineServiceRequest.Status.ACCEPTED, MachineServiceRequest.Status.IN_PROGRESS,
                   MachineServiceRequest.Status.COMPLETED)


def snapshot(row):
    machine_type = usage.type_of(row)
    profile = usage.definitions(row.makerspace, machine_type).select_related("consumable_pool", "product")
    actuals = usage.latest(row, usage.ACTUAL)
    recorded = {item.definition_id for item in actuals}
    return {"profile": profile, "estimates": usage.latest(row, usage.ESTIMATE), "actuals": actuals,
            "missing_required": [item.key for item in profile if item.required and item.pk not in recorded]}


def _entries(validated):
    return [{"key": item["key"], "quantity": item["quantity"], "attributes": item.get("attributes") or {}}
            for item in validated]


class StaffJobConsumablesView(APIView):
    permission_classes = [IsActiveStaff]

    def _job(self, request, makerspace_id, pk):
        from apps.admin_api.views_machine_service_common import _manageable_request
        row = _manageable_request(request.user, pk)
        if row.makerspace_id != makerspace_id:
            raise NotFound()
        return row

    @extend_schema(tags=["Admin machine service"], summary="A job's profile consumables: estimates and actuals",
                   responses={200: JobConsumablesSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        return Response(JobConsumablesSerializer(snapshot(self._job(request, makerspace_id, pk))).data)

    @extend_schema(tags=["Admin machine service"], summary="Record estimates or actual use for a job",
                   description="Actuals are recorded once per consumable and draw linked stock; an identical "
                               "repeat is a no-op, a different one answers 400 consumable_already_recorded.",
                   request=RecordConsumablesSerializer, responses={200: JobConsumablesSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        row = self._job(request, makerspace_id, pk)
        payload = RecordConsumablesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        entries = _entries(payload.validated_data["entries"])
        with transaction.atomic():
            locked = MachineServiceRequest.objects.select_for_update(no_key=True, of=("self",)).get(pk=row.pk)
            if payload.validated_data["phase"] == "estimate":
                usage.record_estimates(locked, request.user, entries, source="staff")
            else:
                usage.record_actuals(locked, request.user, entries, source="staff")
        return Response(JobConsumablesSerializer(snapshot(row)).data)


class MemberJobConsumablesView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(tags=["Public machine service"], summary="Report what your own job used",
                   description="Only consumables this machine type lets members report, once each.",
                   request=ConsumableEntrySerializer(many=True), responses={200: JobConsumableUsageSerializer(many=True), **ERRORS})
    def post(self, request, pk):
        from .views_service_cancel import _owned, _require_owner_session
        user = _require_owner_session(request)
        row = _owned(user, Q(pk=pk))
        payload = ConsumableEntrySerializer(data=request.data, many=True)
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            locked = MachineServiceRequest.objects.select_for_update(no_key=True, of=("self",)).get(pk=row.pk)
            if locked.status not in MEMBER_STATUSES:
                raise ValidationError({"detail": gettext("You can report use once staff have accepted the job."),
                                       "code": "job_not_running"})
            usage.record_actuals(locked, user, _entries(payload.validated_data), source="member")
        return Response(JobConsumableUsageSerializer(usage.latest(row, usage.ACTUAL), many=True).data)
