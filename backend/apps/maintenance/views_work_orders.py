"""Work-order routes (machines D7, MT3): list, create, edit, move and assign.

Rows are scoped by subject: machine work orders through the actor's machine scope,
item ones through `edit_inventory`, room ones through `manage_bookings`; each subject
kind only while its parent's maintenance switch is on (#128 C-9).
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled

from . import work_orders as service
from .models import WorkOrder

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404)}


class WorkOrderSerializer(serializers.ModelSerializer):
    subject_id = serializers.SerializerMethodField()
    subject_label = serializers.SerializerMethodField()
    assignee_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = WorkOrder
        fields = ["id", "subject_type", "subject_id", "subject_label", "title", "description", "priority", "status",
                  "takes_machine_down", "due_on", "assignee_id", "resolution", "schedule_id", "log_id",
                  "created_at", "updated_at", "started_at", "closed_at"]
        read_only_fields = fields

    def get_subject_id(self, row) -> int:
        return row.machine_id or row.product_id or row.asset_id or row.space_id

    def get_subject_label(self, row) -> str:
        subject = row.subject
        return getattr(subject, "name", "") or getattr(subject, "asset_tag", "") or str(subject)


class WorkOrderCreateSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(choices=WorkOrder.Subject.choices)
    subject_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=WorkOrder.Priority.choices, default="normal")
    due_on = serializers.DateField(required=False, allow_null=True, default=None)
    takes_machine_down = serializers.BooleanField(default=False)


class WorkOrderMoveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[S for S in WorkOrder.Status.values if S != "open"])
    resolution = serializers.CharField(required=False, allow_blank=True, default="")
    cost = serializers.DecimalField(required=False, allow_null=True, max_digits=12, decimal_places=2, min_value=0,
                                    default=None)
    parts_note = serializers.CharField(required=False, allow_blank=True, default="")


class WorkOrderAssignSerializer(serializers.Serializer):
    assignee_id = serializers.IntegerField(allow_null=True, min_value=1)


def _subject(space, subject_type, pk):
    from apps.bookings.models import BookableSpace
    from apps.inventory.models import InventoryAsset, InventoryProduct
    from apps.machines.models import Machine
    model = {"machine": Machine, "inventory_product": InventoryProduct, "inventory_asset": InventoryAsset,
             "bookable_space": BookableSpace}[subject_type]
    return get_object_or_404(model.objects.filter(makerspace=space), pk=pk)


def visible(actor, space):
    from apps.machines.access import scope_machines_for_actor
    from apps.machines.models import Machine
    rows, allowed = WorkOrder.objects.filter(makerspace=space), Q(pk__in=[])
    if feature_enabled(space, "machines.maintenance"):
        machines = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space)).values("pk")
        allowed |= Q(subject_type="machine", machine_id__in=machines)
    if feature_enabled(space, "inventory.maintenance") and rbac.can(actor, rbac.Action.EDIT_INVENTORY, space.pk):
        allowed |= Q(subject_type__in=("inventory_product", "inventory_asset"))
    if feature_enabled(space, "bookings.room_maintenance") and rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, space.pk):
        allowed |= Q(subject_type="bookable_space")
    return rows.filter(allowed)


def _space(actor, makerspace_id):
    return get_object_or_404(rbac.scope_by_makerspace(actor, Makerspace.objects.all(), makerspace_field="pk"),
                             pk=makerspace_id)


def _order(actor, pk):
    row = get_object_or_404(rbac.scope_by_makerspace(actor, WorkOrder.objects.select_related("makerspace")), pk=pk)
    return get_object_or_404(visible(actor, row.makerspace), pk=row.pk)


class WorkOrderListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin maintenance"], summary="Work orders in my scope",
                   parameters=[OpenApiParameter("status", str, required=False),
                               OpenApiParameter("machine", int, required=False)],
                   responses={200: WorkOrderSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        rows = visible(request.user, _space(request.user, makerspace_id))
        if status_value := request.query_params.get("status"):
            rows = rows.filter(status__in=status_value.split(","))
        if (machine := request.query_params.get("machine")) and str(machine).isdigit():
            rows = rows.filter(machine_id=int(machine))
        return Response(WorkOrderSerializer(rows.select_related("machine", "product", "asset", "space")[:300],
                                            many=True).data)

    @extend_schema(tags=["Admin maintenance"], summary="Open a work order",
                   request=WorkOrderCreateSerializer, responses={201: WorkOrderSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        payload = WorkOrderCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        subject = _subject(space, data["subject_type"], data.pop("subject_id"))
        order = service.create_work_order(request.user, space, subject=subject, **data)
        return Response(WorkOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class WorkOrderMoveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin maintenance"], summary="Start, hold, close or cancel a work order",
                   request=WorkOrderMoveSerializer, responses={200: WorkOrderSerializer, **ERRORS})
    def post(self, request, pk):
        order = _order(request.user, pk)
        payload = WorkOrderMoveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        order = service.move(request.user, order, data["status"], resolution=data["resolution"],
                             log_cost=data["cost"], parts_note=data["parts_note"])
        return Response(WorkOrderSerializer(order).data)


class WorkOrderAssignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin maintenance"], summary="Assign a work order to a staff member (or clear it)",
                   request=WorkOrderAssignSerializer, responses={200: WorkOrderSerializer, **ERRORS})
    def post(self, request, pk):
        from apps.accounts.models import User
        order = _order(request.user, pk)
        payload = WorkOrderAssignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        assignee_id = payload.validated_data["assignee_id"]
        assignee = User.objects.filter(pk=assignee_id).first() if assignee_id else None
        if assignee_id and assignee is None:
            raise serializers.ValidationError({"assignee_id": "Assign a staff member of this makerspace."})
        return Response(WorkOrderSerializer(service.assign(request.user, order, assignee)).data)
