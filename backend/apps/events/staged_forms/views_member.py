"""Owner routes; a known response ID never substitutes for ownership."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from .http import PrivateView, body, member_event, paginated
from . import serializers as s
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .projections import assignment_summary, detail
from .response_workflow import prepare, save, schema_context
from .trigger_service import resolve_participant
from .transactions import command
from .stage_workflow import activate_locked
from apps.payments.event_payouts.errors import require


class StageFormListView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageAssignmentSerializer(many=True), **s.ERRORS})
    def get(self, request, makerspace_id, pk):
        event = member_event(request, pk, makerspace_id)
        rows = StageFormAssignment.objects.filter(event=event, owner_member=request.user).select_related("stage_form", "response").order_by("pk")
        return paginated(request, rows, assignment_summary)


class StageFormContextView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageResponseDetailSerializer, **s.ERRORS})
    def get(self, request, makerspace_id, pk, stage_form_id):
        from .trigger_service import applicable
        event = member_event(request, pk, makerspace_id)
        definition = get_object_or_404(EventStageForm, pk=stage_form_id, event=event)
        row = StageFormAssignment.objects.filter(stage_form=definition, owner_member=request.user).first()
        if row:
            return Response({**detail(actor=request.user, response=row.response, owner=True), "schema": schema_context(row.response)})
        subject = resolve_participant(event=event, owner_id=request.user.pk)
        require(applicable(definition, subject) is not None, "stage_not_applicable", status=404)
        return Response({"stage_form_id": definition.pk, "schema": definition.current_revision.schema,
                         "event_date_revision": event.event_date_revision, "response_id": None})


class StageDraftView(PrivateView):
    @extend_schema(tags=["Event stage forms"], request=s.StageDraftCommand,
                   responses={201: s.StageResponseDetailSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, pk, stage_form_id):
        event = member_event(request, pk, makerspace_id)
        data = body(request, s.StageDraftCommand)
        with command(event_id=event.pk, actor=request.user, data=data, action=f"stage.draft:{stage_form_id}", owner=True) as ctx:
            if ctx.replay:
                return Response(ctx.replay)
            definition = EventStageForm.objects.select_for_update().get(pk=stage_form_id, event=ctx.event)
            ctx.cas(definition)
            # Standalone draft needs real canonical participation; virtual child
            # creation is an in-process outer-transaction bridge, never HTTP proof.
            subject = resolve_participant(event=ctx.event, owner_id=ctx.actor.pk)
            require(subject.registration is not None or subject.application is not None, "canonical_participation_required")
            row = activate_locked(definition=definition, subject=subject, locks=ctx.locks)
            require(row is not None, "stage_not_applicable")
            ctx.audit("event.stage_form.draft_created", row, assignment_id=row.pk, response_id=row.response.pk)
            return Response(ctx.finish(row, response_id=row.response.pk, response_version=row.response.version), status=201)


class StageResponseView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageResponseDetailSerializer, **s.ERRORS})
    def get(self, request, makerspace_id, pk, response_id):
        event = member_event(request, pk, makerspace_id)
        response = get_object_or_404(StageFormResponse, pk=response_id, event=event, owner_member=request.user)
        return Response(detail(actor=request.user, response=response, owner=True))

    @extend_schema(tags=["Event stage forms"], request=s.StageResponseCommand,
                   responses={200: s.StageResponseDetailSerializer, **s.ERRORS})
    def put(self, request, makerspace_id, pk, response_id):
        return save_response(request, makerspace_id, pk, response_id, submit=False)


class StageResponseSubmitView(PrivateView):
    @extend_schema(tags=["Event stage forms"], request=s.StageResponseCommand,
                   responses={200: s.StageResponseDetailSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, pk, response_id):
        return save_response(request, makerspace_id, pk, response_id, submit=True)


def save_response(request, makerspace_id, pk, response_id, *, submit):
    event = member_event(request, pk, makerspace_id)
    data = body(request, s.StageResponseCommand)
    response = get_object_or_404(StageFormResponse.objects.select_related("event", "form_revision", "assignment"),
        pk=response_id, event=event, owner_member=request.user)
    prepared = prepare(response=response, actor=request.user, data=data, operation_id=data["operation_id"])
    return Response(save(event_id=pk, actor=request.user, response_id=response_id,
                         data=data, prepared=prepared, submit=submit))
