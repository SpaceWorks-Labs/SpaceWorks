"""Staff job-flow actions (#141, #142): needs changes, quotes, the board edits, batches,
and Not collected. Every action resolves the job through the machine partition (manage
scope), and every state change goes through the machines workflow."""

from django.utils.translation import gettext
from decimal import Decimal

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_machine_service import MachineServiceRequestSerializer
from apps.admin_api.views_machine_service_common import (
    SERVICE_ERRORS, _manage_queryset, _manageable_request, _readable_or_collectable_request, _response,
    _visible_makerspace,
)
from apps.machines import service_workflow_board as board, service_workflow_review as review
from apps.machines.models import MachineConsumablePool, MachineJobBatch
from apps.machines.service_workflow_batch import complete_batch, start_batch
from apps.machines.service_workflow_collect import mark_uncollected

JOB = {200: MachineServiceRequestSerializer, **SERVICE_ERRORS}


class ChangesSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=review.CHANGE_CODES)
    message = serializers.CharField(max_length=4000)


class JobQuoteRequestSerializer(serializers.Serializer):
    estimated_minutes = serializers.IntegerField(min_value=0, max_value=100000)
    quantity = serializers.DecimalField(required=False, allow_null=True, max_digits=12, decimal_places=2,
                                        min_value=Decimal("0"))
    consumable_pool_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")
    # Decision 341: staff estimates for the type's profile consumables, priced into the quote.
    consumable_estimates = serializers.ListField(child=serializers.DictField(), required=False, max_length=32,
                                                 default=list)


class ReorderSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=1)


class UrgentSerializer(serializers.Serializer):
    urgent = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class AssignSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField(allow_null=True, min_value=1)


class _JobAction(APIView):
    permission_classes = [IsActiveStaff]

    def job(self, request, pk, serializer=None):
        row = _manageable_request(request.user, pk)
        data = {}
        if serializer is not None:
            payload = serializer(data=request.data)
            payload.is_valid(raise_exception=True)
            data = payload.validated_data
        return row, data


class RequestChangesView(_JobAction):
    @extend_schema(tags=["Admin machine service"], summary="Ask the member for changes (needs changes)",
                   request=ChangesSerializer, responses=JOB)
    def post(self, request, pk):
        row, data = self.job(request, pk, ChangesSerializer)
        return _response(review.request_changes(row, request.user, **data))


class SendQuoteView(_JobAction):
    @extend_schema(tags=["Admin machine service"], summary="Send a quote priced by the space's rate card",
                   description="Valid 7 days; the member approves the exact price shown (409 price_changed "
                               "otherwise). Re-sending replaces the open quote.",
                   request=JobQuoteRequestSerializer, responses=JOB)
    def post(self, request, pk):
        row, data = self.job(request, pk, JobQuoteRequestSerializer)
        pool = None
        if data.get("consumable_pool_id"):
            pool = get_object_or_404(MachineConsumablePool.objects.filter(makerspace_id=row.makerspace_id),
                                     pk=data["consumable_pool_id"])
        return _response(review.send_quote(row, request.user, estimated_minutes=data["estimated_minutes"],
                                           quantity=data.get("quantity"), pool=pool, note=data["note"],
                                           consumable_estimates=data.get("consumable_estimates")))


class QueueNowView(_JobAction):
    @extend_schema(tags=["Admin machine service"], summary="Queue a prepaid job whose charge is settled",
                   request=None, responses=JOB)
    def post(self, request, pk):
        row, _ = self.job(request, pk)
        return _response(review.promote_prepaid(row, actor=request.user) or row)


class ReorderView(_JobAction):
    @extend_schema(tags=["Admin machine service"], summary="Move a queued job to a position in its queue",
                   request=ReorderSerializer, responses=JOB)
    def post(self, request, pk):
        row, data = self.job(request, pk, ReorderSerializer)
        return _response(board.reorder(row, request.user, position=data["position"]))


class UrgentView(_JobAction):
    @extend_schema(tags=["Admin machine service"], summary="Pin a job as urgent (with a reason) or unpin it",
                   request=UrgentSerializer, responses=JOB)
    def post(self, request, pk):
        row, data = self.job(request, pk, UrgentSerializer)
        return _response(board.pin_urgent(row, request.user, **data))


class AssignView(_JobAction):
    @extend_schema(tags=["Admin machine service"], summary="Pre-assign a waiting job to a machine (or clear it)",
                   request=AssignSerializer, responses=JOB)
    def post(self, request, pk):
        row, data = self.job(request, pk, AssignSerializer)
        return _response(board.assign_machine(row, request.user, machine_id=data["machine_id"]))


class UncollectedView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machine service"], summary="Mark a finished job Not collected (from day 14)",
                   request=None, responses=JOB)
    def post(self, request, pk):
        return _response(mark_uncollected(_readable_or_collectable_request(request.user, pk), request.user))


class BatchStartSerializer(serializers.Serializer):
    job_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=2, max_length=50)
    machine_id = serializers.IntegerField(min_value=1)
    plans = serializers.DictField(child=serializers.DictField(), required=False, default=dict,
                                  help_text="Per job id: estimated_minutes, consumable_pool_id, planned_grams or "
                                            "planned_quantity -- each job's share, adjustable by staff.")
    note = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class BatchCompleteSerializer(serializers.Serializer):
    actual_minutes = serializers.IntegerField(min_value=0)
    actual_quantity = serializers.DecimalField(required=False, allow_null=True, max_digits=12, decimal_places=2,
                                               min_value=Decimal("0"))
    splits = serializers.DictField(required=False, default=dict)
    pickup_location = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")


class BatchResponseSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    jobs = MachineServiceRequestSerializer(many=True)


class BatchStartView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machine service"], summary="Start several queued jobs on one machine run",
                   request=BatchStartSerializer, responses={200: BatchResponseSerializer, **SERVICE_ERRORS})
    def post(self, request, makerspace_id):
        space = _visible_makerspace(request.user, makerspace_id)
        payload = BatchStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        jobs = list(_manage_queryset(request.user, space.pk).filter(pk__in=data["job_ids"]))
        if len(jobs) != len(set(data["job_ids"])):
            raise serializers.ValidationError({"job_ids": gettext("Every job must be one you manage in this makerspace.")})
        plans = {int(key): value for key, value in data["plans"].items()}
        batch, started = start_batch(jobs, request.user, machine_id=data["machine_id"], plans=plans,
                                     note=data["note"])
        return Response({"batch_id": batch.pk, "jobs": [_response(row).data for row in started]})


class BatchCompleteView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machine service"], summary="Finish a batch run; time and material are split",
                   request=BatchCompleteSerializer, responses={200: BatchResponseSerializer, **SERVICE_ERRORS})
    def post(self, request, pk):
        batch = get_object_or_404(MachineJobBatch.objects.all(), pk=pk)
        space = _visible_makerspace(request.user, batch.makerspace_id)
        running = batch.jobs.filter(status="in_progress").values_list("pk", flat=True)
        if _manage_queryset(request.user, space.pk).filter(pk__in=list(running)).count() != len(running):
            raise serializers.ValidationError({"batch": gettext("This batch has jobs outside your machine scope.")})
        payload = BatchCompleteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        splits = {field: {int(key): value for key, value in values.items()}
                  for field, values in data["splits"].items()}
        done = complete_batch(batch, request.user, actual_minutes=data["actual_minutes"],
                              actual_quantity=data.get("actual_quantity"), splits=splits,
                              pickup_location=data["pickup_location"])
        return Response({"batch_id": batch.pk, "jobs": [_response(row).data for row in done]})
