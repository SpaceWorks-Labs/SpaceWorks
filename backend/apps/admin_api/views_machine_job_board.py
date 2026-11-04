"""The per-type queue board (#141) and the per-type job settings (#140, #142)."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_machine_service import MachineServiceRequestSerializer
from apps.admin_api.views_machine_service_common import SERVICE_ERRORS, _manage_queryset, _visible_makerspace
from apps.machines import job_policy, role_scope
from apps.machines.job_order import ordering
from apps.machines.lockout import blocking_schedules
from apps.machines.models import Machine, MachineServiceRequest, MachineType, MakerspaceMachineTypePolicy
from apps.payments.models import Payment

Status = MachineServiceRequest.Status
SETTING_KEYS = {
    "accepts_job_requests": "job_requests.accepts", "max_open_jobs": "job_requests.limits",
    "max_job_minutes": "job_requests.limits", "runs_unattended": "job_requests.unattended",
    "file_groups": "job_requests.file_formats", "quote_mode": "charges.machines_quotes",
    "quote_above_amount": "charges.machines_quotes", "payment_timing": "charges.machines_payment_timing",
    "member_fault_charge": "charges.machines_failure",
}
FILE_GROUPS = ("fab-2d", "fab-3dprint", "fab-cnc", "hardware-cad", "hardware-pcb", "embroidery")


class JobSettingsSerializer(serializers.ModelSerializer):
    file_groups = serializers.ListField(child=serializers.ChoiceField(choices=FILE_GROUPS), required=False,
                                        max_length=len(FILE_GROUPS))

    class Meta:
        model = MakerspaceMachineTypePolicy
        fields = list(SETTING_KEYS)


class BoardLaneSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    status = serializers.CharField()
    locked_out = serializers.BooleanField()
    running = MachineServiceRequestSerializer(many=True)
    assigned = MachineServiceRequestSerializer(many=True)


class BoardSerializer(serializers.Serializer):
    machine_type_id = serializers.IntegerField()
    lanes = BoardLaneSerializer(many=True)
    queue = MachineServiceRequestSerializer(many=True)
    review = MachineServiceRequestSerializer(many=True)
    waiting_on_member = MachineServiceRequestSerializer(many=True)
    ready = MachineServiceRequestSerializer(many=True)
    overdue_pickup_ids = serializers.ListField(child=serializers.IntegerField())
    no_show_member_ids = serializers.ListField(child=serializers.IntegerField())


def _machine_type(space, type_id):
    return get_object_or_404(MachineType.objects.filter(Q(makerspace__isnull=True) | Q(makerspace=space)),
                             pk=type_id)


class JobBoardView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machine service"], summary="Queue board for one machine type",
                   parameters=[OpenApiParameter("machine_type_id", int, required=True)],
                   responses={200: BoardSerializer, **SERVICE_ERRORS})
    def get(self, request, makerspace_id):
        from apps.machines.service_queue_eta import queue_snapshot_for
        space = _visible_makerspace(request.user, makerspace_id)
        type_id = request.query_params.get("machine_type_id")
        machine_type = _machine_type(space, int(type_id) if str(type_id).isdigit() else 0)
        typed = Q(queue__machine_type=machine_type) | Q(bucket__machine__machine_type=machine_type)
        jobs = _manage_queryset(request.user, space.pk).filter(typed)
        live = list(jobs.filter(status__in=(Status.PENDING, Status.ACCEPTED, Status.IN_PROGRESS,
                                            Status.CHANGES_REQUESTED, Status.QUOTED, Status.COMPLETED)).order_by(*ordering()))
        scope = role_scope.scope_q_for(role_scope.manage_scope_for(request.user, space.pk),
                                       machine_id_paths=("pk",), type_id_paths=("machine_type_id",))
        machines = list(Machine.objects.filter(scope, makerspace=space, machine_type=machine_type, is_active=True))
        context = {"queue_snapshot": queue_snapshot_for(live, machines=machines), "payments_by_subject_id": {
            payment.subject_id: payment for payment in Payment.objects.filter(
                makerspace=space, subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST,
                subject_id__in=[row.pk for row in live])}}
        by_status = {status: [row for row in live if row.status == status] for status in Status.values}
        lanes = [{"machine_id": machine.pk, "machine_name": machine.name, "status": machine.status,
                  "locked_out": bool(blocking_schedules(machine)),
                  "running": [row for row in by_status[Status.IN_PROGRESS] if row.assigned_machine_id == machine.pk],
                  "assigned": [row for row in by_status[Status.ACCEPTED] if row.preassigned_machine_id == machine.pk]}
                 for machine in machines]
        cutoff = timezone.now() - timedelta(days=job_policy.UNCOLLECTED_AFTER_DAYS)
        ready = by_status[Status.COMPLETED]
        members = {row.member_id for row in live if row.member_id}
        data = {
            "machine_type_id": machine_type.pk, "lanes": lanes,
            "queue": [row for row in by_status[Status.ACCEPTED] if not row.preassigned_machine_id],
            "review": by_status[Status.PENDING],
            "waiting_on_member": by_status[Status.CHANGES_REQUESTED] + by_status[Status.QUOTED],
            "ready": ready,
            "overdue_pickup_ids": [row.pk for row in ready if row.completed_at and row.completed_at <= cutoff],
            "no_show_member_ids": _no_shows(space, members),
        }
        return Response(BoardSerializer(data, context=context).data)


def _no_shows(space, members):
    from django.db.models import Count
    since = timezone.now() - timedelta(days=job_policy.NO_SHOW_WINDOW_DAYS)
    rows = MachineServiceRequest.objects.filter(
        makerspace=space, member_id__in=members, status=Status.UNCOLLECTED, uncollected_at__gte=since,
    ).values("member_id").annotate(total=Count("pk")).filter(total__gte=job_policy.NO_SHOW_LIMIT)
    return sorted(row["member_id"] for row in rows)


class JobSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    def resolve(self, request, makerspace_id, type_id):
        space = _visible_makerspace(request.user, makerspace_id, rbac.Action.MANAGE_MACHINES)
        machine_type = _machine_type(space, type_id)
        return space, machine_type, job_policy.policy_for(space, machine_type)

    @extend_schema(tags=["Admin machine service"], summary="Job settings for one machine type",
                   responses={200: JobSettingsSerializer, **SERVICE_ERRORS})
    def get(self, request, makerspace_id, type_id):
        _space, _type, policy = self.resolve(request, makerspace_id, type_id)
        return Response(JobSettingsSerializer(policy).data)

    @extend_schema(tags=["Admin machine service"], summary="Change the job settings for one machine type",
                   description="Through the settings-authority layer: money choices (quotes, prepay, failure "
                               "charging) are the Space Manager's alone.",
                   request=JobSettingsSerializer, responses={200: JobSettingsSerializer, **SERVICE_ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id, type_id):
        from apps.audit import services as audit
        from apps.makerspaces.settings_authority import assert_setting_write, record_change
        space, machine_type, policy = self.resolve(request, makerspace_id, type_id)
        before = JobSettingsSerializer(policy).data
        payload = JobSettingsSerializer(policy, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        changed = [key for key, value in payload.validated_data.items() if getattr(policy, key) != value]
        decisions = {key: assert_setting_write(request.user, space, "machines", SETTING_KEYS[key]) for key in changed}
        policy = payload.save(makerspace=space, machine_type=machine_type)
        after = JobSettingsSerializer(policy).data
        for key, decision in decisions.items():
            record_change(request.user, space, "machines", SETTING_KEYS[key], before.get(key), after.get(key), decision)
        if changed:
            audit.record(request.user, "machine_type.job_settings_updated", makerspace=space, target=policy,
                         meta={"machine_type_id": machine_type.pk, "fields": sorted(changed)})
        return Response(after)
