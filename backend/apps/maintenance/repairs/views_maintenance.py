"""Item and room maintenance schedules, runs, a Technician's due list, and room outages."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.maintenance.serializers_cost import MaintenanceCostFields

from . import areas, authority, maintenance_subjects as svc
from .models_service import RoomOutage, SubjectMaintenanceLog, SubjectMaintenanceSchedule
from .views_common import ERRORS, require_any, space_for

TAGS = ["Repairs maintenance"]
ITEM_ROOM = {areas.INVENTORY: areas.MAINTENANCE[areas.INVENTORY], areas.ROOMS: areas.MAINTENANCE[areas.ROOMS]}


class SubjectScheduleSerializer(serializers.ModelSerializer):
    subject_id = serializers.SerializerMethodField()
    subject_label = serializers.SerializerMethodField()

    class Meta:
        model = SubjectMaintenanceSchedule
        fields = ["id", "subject_type", "subject_id", "subject_label", "description", "interval_days", "next_due",
                  "is_active", "created_at", "updated_at"]

    def get_subject_id(self, row) -> int:
        return row.product_id or row.asset_id or row.room_id

    def get_subject_label(self, row) -> str:
        subject = row.asset or row.product or row.room
        return getattr(subject, "name", "") or getattr(subject, "asset_tag", "") or str(subject)


class SubjectScheduleWriteSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(choices=list(svc.FIELDS), required=False)
    subject_id = serializers.IntegerField(min_value=1, required=False)
    description = serializers.CharField(max_length=2000, required=False)
    interval_days = serializers.IntegerField(min_value=1, max_value=3650, required=False)
    next_due = serializers.DateField(required=False)
    is_active = serializers.BooleanField(required=False)


class MaintenanceRunSerializer(MaintenanceCostFields):
    summary = serializers.CharField(max_length=4000)
    parts_note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, allow_null=True, required=False,
                                    default=None, help_text="What the run cost; above zero it reaches the ledger.")


class SubjectLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubjectMaintenanceLog
        fields = ["id", "schedule_id", "subject_type", "performed_at", "summary", "parts_note", "cost"]


class MachineDueSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    description = serializers.CharField()
    next_due = serializers.DateField()


class MyMaintenanceSerializer(serializers.Serializer):
    machine_schedules = MachineDueSerializer(many=True)
    schedules = SubjectScheduleSerializer(many=True)


class RoomOutageSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source="room.name", read_only=True)

    class Meta:
        model = RoomOutage
        fields = ["id", "room_id", "room_name", "mode", "reason", "expected_back_at", "started_at", "ended_at",
                  "issue_id"]


class SubjectScheduleListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Item and room maintenance schedules I manage or cover",
                   responses={200: SubjectScheduleSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        require_any(space, ITEM_ROOM)
        return Response(SubjectScheduleSerializer(svc.visible_schedules(request.user, space), many=True).data)

    @extend_schema(tags=TAGS, summary="Add an item or room maintenance schedule",
                   request=SubjectScheduleWriteSerializer, responses={201: SubjectScheduleSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        body = SubjectScheduleWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        missing = {"subject_type", "subject_id", "description", "interval_days", "next_due"} - set(data)
        if missing:
            raise serializers.ValidationError({name: "This field is required." for name in sorted(missing)})
        subject = get_object_or_404(areas.subject_model(data["subject_type"]).objects.filter(makerspace=space),
                                    pk=data["subject_id"])
        row = svc.create_schedule(request.user, space, subject_type=data["subject_type"], subject=subject,
                                  description=data["description"], interval_days=data["interval_days"],
                                  next_due=data["next_due"])
        return Response(SubjectScheduleSerializer(row).data, status=status.HTTP_201_CREATED)


def _schedule(actor, pk):
    return get_object_or_404(rbac.scope_by_makerspace(actor, SubjectMaintenanceSchedule.objects.select_related(
        "makerspace", "product", "asset", "room")), pk=pk)


class SubjectScheduleDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Change or pause an item or room schedule",
                   request=SubjectScheduleWriteSerializer, responses={200: SubjectScheduleSerializer, **ERRORS})
    def patch(self, request, pk):
        body = SubjectScheduleWriteSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        data = {key: value for key, value in body.validated_data.items()
                if key in ("description", "interval_days", "next_due", "is_active")}
        return Response(SubjectScheduleSerializer(svc.update_schedule(request.user, _schedule(request.user, pk),
                                                                      **data)).data)


class SubjectScheduleRunView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Log a maintenance run (the next due date moves on)",
                   request=MaintenanceRunSerializer, responses={201: SubjectLogSerializer, **ERRORS})
    def post(self, request, pk):
        body = MaintenanceRunSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        log = svc.run(request.user, _schedule(request.user, pk), **body.validated_data)
        return Response(SubjectLogSerializer(log).data, status=status.HTTP_201_CREATED)


class MachineScheduleRunView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Complete a machine maintenance schedule (manager or covering Technician)",
                   request=MaintenanceRunSerializer, responses={201: SubjectLogSerializer, **ERRORS})
    def post(self, request, pk):
        from apps.maintenance.models import MaintenanceSchedule
        body = MaintenanceRunSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        schedule = get_object_or_404(rbac.scope_by_makerspace(
            request.user, MaintenanceSchedule.objects.select_related("machine"),
            makerspace_field="machine__makerspace_id"), pk=pk)
        log = svc.run_machine_schedule(request.user, schedule, **body.validated_data)
        return Response({"id": log.pk, "schedule_id": schedule.pk, "subject_type": "machine",
                         "performed_at": log.performed_at, "summary": log.summary, "parts_note": log.parts_note,
                         "cost": log.cost},
                        status=status.HTTP_201_CREATED)


class MyMaintenanceView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Maintenance due in my coverage (machines, items, rooms)",
                   responses={200: MyMaintenanceSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.maintenance.models import MaintenanceSchedule
        space = space_for(request.user, makerspace_id)
        require_any(space, areas.MAINTENANCE)
        contact = authority.contact_for(request.user, space.pk)
        machine_rows = []
        if areas.on(space, areas.MAINTENANCE[areas.MACHINES]) and contact is not None and rbac.can(
                request.user, rbac.Action.RUN_MAINTENANCE, space.pk):
            for row in MaintenanceSchedule.objects.filter(machine__makerspace=space, is_active=True).select_related(
                    "machine").order_by("next_due", "id")[:500]:
                if authority.covers(contact, "machine", row.machine):
                    machine_rows.append({"id": row.pk, "machine_id": row.machine_id, "machine_name": row.machine.name,
                                         "description": row.description, "next_due": row.next_due})
        return Response({"machine_schedules": machine_rows, "schedules": SubjectScheduleSerializer(
            svc.visible_schedules(request.user, space), many=True).data})


class RoomOutageListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Room outages (open first)", responses={200: RoomOutageSerializer(many=True),
                                                                             **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        if not (areas.on(space, areas.REPAIRS[areas.ROOMS]) or areas.on(space, areas.MAINTENANCE[areas.ROOMS])):
            areas.refuse(areas.REPAIRS[areas.ROOMS])
        if not areas.manager_may(request.user, space.pk, "bookable_space") and not rbac.can(
                request.user, rbac.Action.SET_SERVICE_STATE, space.pk):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        rows = RoomOutage.objects.filter(makerspace=space).select_related("room").order_by("ended_at", "-started_at")
        return Response(RoomOutageSerializer(rows[:200], many=True).data)
