"""Organizer status is separate from organizer/finance answer disclosure."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.response import Response
from apps.accounts import rbac
from apps.events import event_authority
from apps.events.models import Event
from apps.payments.event_payouts.errors import require
from .http import PrivateView, body, paginated
from . import serializers as s
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .projections import assignment_summary, detail
from . import stage_workflow, assignment_workflow, milestone_workflow


class StageDefinitionListView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageDefinitionSerializer(many=True), **s.ERRORS})
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, "edit_details")
        return paginated(request, EventStageForm.objects.filter(event=event).order_by("pk"),
                         lambda row: s.StageDefinitionSerializer(row).data)

    @extend_schema(tags=["Event stage forms"], request=s.StageConfigurationCommand,
                   responses={201: s.StageDefinitionSerializer, **s.ERRORS})
    def post(self, request, pk):
        return Response(stage_workflow.configure(event_id=pk, actor=request.user,
            data=body(request, s.StageConfigurationCommand)), status=201)


class StageDefinitionDetailView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageDefinitionSerializer, **s.ERRORS})
    def get(self, request, pk, stage_form_id):
        event = event_authority.get_event(request.user, pk, "edit_details")
        row = get_object_or_404(EventStageForm, event=event, pk=stage_form_id)
        return Response({**s.StageDefinitionSerializer(row).data,
                         "schema": row.current_revision.schema if row.current_revision_id else None})

    @extend_schema(tags=["Event stage forms"], request=s.StageConfigurationCommand,
                   responses={200: s.StageDefinitionSerializer, **s.ERRORS})
    def patch(self, request, pk, stage_form_id):
        return Response(stage_workflow.configure(event_id=pk, actor=request.user, stage_form_id=stage_form_id,
            data=body(request, s.StageConfigurationCommand)))


class StageTransitionView(PrivateView):
    publish = True

    @extend_schema(tags=["Event stage forms"], request=s.StageCommand,
                   responses={200: s.StageDefinitionSerializer, **s.ERRORS})
    def post(self, request, pk, stage_form_id):
        return Response(stage_workflow.transition(event_id=pk, actor=request.user, stage_form_id=stage_form_id,
            data=body(request, s.StageCommand), publish=self.publish))


class StageAssignmentListView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageAssignmentSerializer(many=True), **s.ERRORS})
    def get(self, request, pk):
        event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk)
        from apps.makerspaces.guards import require_module
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        require_module(event.makerspace, "events")
        assert_write_allowed(event.makerspace_id)
        require(event_authority.can(request.user, event, "manage_registrations") or
                rbac.can(request.user, rbac.Action.VIEW_FINANCE, event.makerspace_id), "permission_denied", status=403)
        return paginated(request, StageFormAssignment.objects.filter(event=event).select_related(
            "stage_form", "response").order_by("pk"), assignment_summary)


class StageActivateView(PrivateView):
    @extend_schema(tags=["Event stage forms"], request=s.StageActivationCommand,
                   responses={200: s.StageDefinitionSerializer, 202: s.StageDefinitionSerializer, **s.ERRORS})
    def post(self, request, pk, stage_form_id):
        data = body(request, s.StageActivationCommand)
        return Response(stage_workflow.request_activation(event_id=pk, actor=request.user,
            stage_form_id=stage_form_id, data=data), status=200 if data["preview"] else 202)


class StageAssignmentCommandView(PrivateView):
    action = "cancel"
    serializer_class = s.CancelStageAssignmentCommand

    @extend_schema(tags=["Event stage forms"], request=s.CancelStageAssignmentCommand,
                   responses={200: s.StageAssignmentSerializer, **s.ERRORS})
    def post(self, request, pk, assignment_id):
        return Response(assignment_workflow.manage(event_id=pk, actor=request.user, assignment_id=assignment_id,
            data=body(request, self.serializer_class), action=self.action))


class StageShortlistView(PrivateView):
    @extend_schema(tags=["Event stage forms"], request=s.ShortlistCommand,
                   responses={200: s.StageDefinitionSerializer, **s.ERRORS})
    def post(self, request, pk):
        return Response(milestone_workflow.shortlist(event_id=pk, actor=request.user, data=body(request, s.ShortlistCommand)))


class StageResponseDetailView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=[OpenApiParameter("revision", int)],
                   responses={200: s.StageResponseDetailSerializer, **s.ERRORS})
    def get(self, request, pk, response_id):
        event = event_authority.get_event(request.user, pk, "manage_registrations")
        response = get_object_or_404(StageFormResponse, pk=response_id, event=event)
        revision = request.query_params.get("revision")
        require(revision is None or revision.isdecimal() and len(revision) <= 10 and int(revision) > 0, "invalid_revision", status=400)
        return Response(detail(actor=request.user, response=response, revision=int(revision) if revision else None))


class StageResponseFinanceDetailView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=[OpenApiParameter("revision", int)],
                   responses={200: s.StageResponseFinanceDetailSerializer, **s.ERRORS})
    def get(self, request, pk, response_id):
        from apps.makerspaces.guards import require_module
        response = get_object_or_404(StageFormResponse.objects.select_related("event__makerspace"), pk=response_id, event_id=pk)
        from apps.payments.event_payouts.authority import authorize
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        authorize(request, response.event.makerspace)
        assert_write_allowed(response.event.makerspace_id)
        require_module(response.event.makerspace, "events")
        revision = request.query_params.get("revision")
        require(revision is None or revision.isdecimal() and len(revision) <= 10 and int(revision) > 0, "invalid_revision", status=400)
        return Response(detail(actor=request.user, response=response, revision=int(revision) if revision else None, finance=True))
