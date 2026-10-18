"""Owner routes; a known response ID never substitutes for ownership."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, PolymorphicProxySerializer
from rest_framework.response import Response
from .http import PrivateView, body, member_event, paginated
from . import serializers as s
from . import serializers_results as result
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .projections import assignment_summary, detail
from .response_workflow import prepare, save, schema_context
from .trigger_service import resolve_participant
from .transactions import command, replay_before_prepare
from .stage_workflow import activate_locked
from apps.payments.event_payouts.errors import require

KEY = [OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)]


class StageFormListView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: result.AssignmentPage, **s.ERRORS})
    def get(self, request, makerspace_id, pk):
        event = member_event(request, pk, makerspace_id)
        rows = StageFormAssignment.objects.filter(event=event, owner_member=request.user).select_related("stage_form", "response", "pinned_form_revision").order_by("pk")
        return paginated(request, rows, assignment_summary)


class StageFormContextView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=[OpenApiParameter("creation_operation_id", str)], responses={200: PolymorphicProxySerializer(
        component_name="StageContext", serializers=[s.StageOwnerResponseSerializer, result.StageVirtualContext],
        resource_type_field_name=None), **s.ERRORS})
    def get(self, request, makerspace_id, pk, stage_form_id):
        from .trigger_service import applicable
        event = member_event(request, pk, makerspace_id)
        definition = get_object_or_404(EventStageForm, pk=stage_form_id, event=event)
        row = StageFormAssignment.objects.filter(stage_form=definition, owner_member=request.user).first()
        if row:
            return Response({**detail(actor=request.user, response=row.response, owner=True), "schema": schema_context(row.response)})
        subject = resolve_participant(event=event, owner_id=request.user.pk)
        creation = request.query_params.get("creation_operation_id")
        if creation:
            from uuid import UUID
            from dataclasses import replace
            from apps.events.contracts.form_operations import child_form_operation_id
            from .trigger_service import require_virtual_context
            try:
                outer = UUID(creation)
            except ValueError:
                require(False, "invalid_creation_operation", status=400)
            require_virtual_context(event, request.user)
            require(definition.stage == "application", "stage_not_inline")
            subject = replace(subject, creation_operation_id=child_form_operation_id(outer,
                event_id=event.pk, owner_id=request.user.pk, slot=f"stage:{definition.pk}"))
        require(applicable(definition, subject) is not None, "stage_not_applicable", status=404)
        return Response({"stage_form_id": definition.pk, "schema": definition.current_revision.schema,
                         "event_date_revision": event.event_date_revision, "response_id": None})


class StageDraftView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageDraftCommand,
                   responses={201: result.StageMutationResult, **s.ERRORS})
    def post(self, request, makerspace_id, pk, stage_form_id):
        event = member_event(request, pk, makerspace_id)
        data = body(request, s.StageDraftCommand)
        with command(event_id=event.pk, actor=request.user, data=data, action=f"stage.draft:{stage_form_id}",
                     owner=True, virtual=bool(data.get("creation_operation_id"))) as ctx:
            if ctx.replay:
                return Response(ctx.replay)
            definition = EventStageForm.objects.select_for_update().get(pk=stage_form_id, event=ctx.event)
            ctx.cas(definition)
            subject = resolve_participant(event=ctx.event, owner_id=ctx.actor.pk)
            if data.get("creation_operation_id"):
                from dataclasses import replace
                from apps.events.contracts.form_operations import child_form_operation_id
                require(definition.stage == "application", "stage_not_inline")
                subject = replace(subject, creation_operation_id=child_form_operation_id(data["creation_operation_id"],
                    event_id=event.pk, owner_id=ctx.actor.pk, slot=f"stage:{definition.pk}"))
            row = activate_locked(definition=definition, subject=subject, locks=ctx.locks)
            require(row is not None, "stage_not_applicable")
            ctx.audit("event.stage_form.draft_created", row, assignment_id=row.pk, response_id=row.response.pk)
            return Response(ctx.finish(row, response_id=row.response.pk, response_version=row.response.version), status=201)


class StageResponseView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageOwnerResponseSerializer, **s.ERRORS})
    def get(self, request, makerspace_id, pk, response_id):
        event = member_event(request, pk, makerspace_id)
        response = get_object_or_404(StageFormResponse, pk=response_id, event=event, owner_member=request.user)
        return Response(detail(actor=request.user, response=response, owner=True))

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageResponseCommand,
                   responses={200: result.StageMutationResult, **s.ERRORS})
    def put(self, request, makerspace_id, pk, response_id):
        return save_response(request, makerspace_id, pk, response_id, submit=False)


class StageResponseSubmitView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageResponseCommand,
                   responses={200: result.StageMutationResult, **s.ERRORS})
    def post(self, request, makerspace_id, pk, response_id):
        return save_response(request, makerspace_id, pk, response_id, submit=True)


def save_response(request, makerspace_id, pk, response_id, *, submit):
    event = member_event(request, pk, makerspace_id)
    data = body(request, s.StageResponseCommand)
    replay = replay_before_prepare(event=event, actor=request.user, data=data,
        action=f"stage_response.{'submit' if submit else 'draft'}:{response_id}")
    if replay:
        return Response(replay)
    response = get_object_or_404(StageFormResponse.objects.select_related("event", "form_revision", "assignment"),
        pk=response_id, event=event, owner_member=request.user)
    prepared = prepare(response=response, actor=request.user, data=data, operation_id=data["operation_id"], draft=not submit)
    return Response(save(event_id=pk, actor=request.user, response_id=response_id,
                         data=data, prepared=prepared, submit=submit))
