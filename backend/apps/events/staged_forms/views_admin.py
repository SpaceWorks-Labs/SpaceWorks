"""Organizer status is separate from organizer/finance answer disclosure."""
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.response import Response
from apps.accounts import rbac
from apps.events import event_authority
from apps.events.models import Event
from apps.payments.event_payouts.errors import require
from .http import PrivateView, body, paginated, staff_event
from . import serializers as s
from . import serializers_results as result
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .projections import assignment_summary, detail
from . import stage_workflow, assignment_workflow, milestone_workflow

KEY = [OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)]


class StageDefinitionListView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: result.DefinitionPage, **s.ERRORS})
    def get(self, request, pk):
        event = staff_event(request, pk, "edit_details")
        return paginated(request, EventStageForm.objects.filter(event=event).order_by("pk"),
                         lambda row: s.StageDefinitionSerializer(row).data)

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageConfigurationCommand,
                   responses={201: result.StageDefinitionResult, **s.ERRORS})
    def post(self, request, pk):
        return Response(stage_workflow.configure(event_id=pk, actor=request.user,
            data=body(request, s.StageConfigurationCommand)), status=201)


class StageDefinitionDetailView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: s.StageDefinitionDetailSerializer, **s.ERRORS})
    def get(self, request, pk, stage_form_id):
        event = staff_event(request, pk, "edit_details")
        row = get_object_or_404(EventStageForm, event=event, pk=stage_form_id)
        return Response({**s.StageDefinitionSerializer(row).data,
                         "schema": row.current_revision.schema if row.current_revision_id else None})

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageConfigurationCommand,
                   responses={200: result.StageDefinitionResult, **s.ERRORS})
    def patch(self, request, pk, stage_form_id):
        return Response(stage_workflow.configure(event_id=pk, actor=request.user, stage_form_id=stage_form_id,
            data=body(request, s.StageConfigurationCommand)))


class StageTransitionView(PrivateView):
    publish = True

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageCommand,
                   responses={200: result.StageDefinitionResult, **s.ERRORS})
    def post(self, request, pk, stage_form_id):
        return Response(stage_workflow.transition(event_id=pk, actor=request.user, stage_form_id=stage_form_id,
            data=body(request, s.StageCommand), publish=self.publish))


class StageAssignmentListView(PrivateView):
    @extend_schema(tags=["Event stage forms"], responses={200: result.AssignmentPage, **s.ERRORS})
    def get(self, request, pk):
        event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk)
        from apps.makerspaces.guards import require_module
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        require_module(event.makerspace, "events")
        assert_write_allowed(event.makerspace_id)
        require(event_authority.can(request.user, event, "manage_registrations") or
                rbac.can(request.user, rbac.Action.VIEW_FINANCE, event.makerspace_id), "permission_denied", status=403)
        return paginated(request, StageFormAssignment.objects.filter(event=event).select_related(
            "stage_form", "response", "pinned_form_revision").filter(
                Q(registration__isnull=False) | Q(application__submitted_at__isnull=False)).order_by("pk"),
            lambda row: completion_summary(row, request.user))


class StageActivateView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.StageActivationCommand,
                   responses={200: result.StageActivationPreview, 202: result.StageActivationResult, **s.ERRORS})
    def post(self, request, pk, stage_form_id):
        data = body(request, s.StageActivationCommand)
        return Response(stage_workflow.request_activation(event_id=pk, actor=request.user,
            stage_form_id=stage_form_id, data=data), status=200 if data["preview"] else 202)


class StageAssignmentCommandView(PrivateView):
    action = "cancel"
    serializer_class = s.CancelStageAssignmentCommand

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.CancelStageAssignmentCommand,
                   responses={200: result.StageMutationResult, **s.ERRORS})
    def post(self, request, pk, assignment_id):
        return Response(assignment_workflow.manage(event_id=pk, actor=request.user, assignment_id=assignment_id,
            data=body(request, self.serializer_class), action=self.action))


class StageShortlistView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.ShortlistCommand,
                   responses={200: result.StageShortlistResult, **s.ERRORS})
    def post(self, request, pk):
        return Response(milestone_workflow.shortlist(event_id=pk, actor=request.user, data=body(request, s.ShortlistCommand)))


class StageReassignView(StageAssignmentCommandView):
    action, serializer_class = "reassign", s.ReassignStageAssignmentCommand

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.ReassignStageAssignmentCommand,
                   responses={200: result.StageMutationResult, **s.ERRORS})
    def post(self, request, pk, assignment_id):
        return super().post(request, pk, assignment_id)


class StageExtendView(StageAssignmentCommandView):
    action, serializer_class = "extend", s.ExtendStageAssignmentCommand

    @extend_schema(tags=["Event stage forms"], parameters=KEY, request=s.ExtendStageAssignmentCommand,
                   responses={200: result.StageMutationResult, **s.ERRORS})
    def post(self, request, pk, assignment_id):
        return super().post(request, pk, assignment_id)


class StageReopenView(StageExtendView):
    action = "reopen"


class StageResponseDetailView(PrivateView):
    @extend_schema(tags=["Event stage forms"], parameters=[OpenApiParameter("revision", int)],
                   responses={200: s.StageResponseDetailSerializer, **s.ERRORS})
    def get(self, request, pk, response_id):
        from apps.accounts.reauthentication import binding
        binding(request)
        event = staff_event(request, pk, "manage_registrations")
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


def completion_summary(row, actor):
    result = assignment_summary(row)
    event = row.event
    from django.core.exceptions import ObjectDoesNotExist
    try:
        response = row.response
    except ObjectDoesNotExist:
        response = None
    organizer = event_authority.can(actor, event, "manage_registrations") and rbac.can(actor, rbac.Action.VIEW_AUDIT, event.makerspace_id)
    finance = rbac.can(actor, rbac.Action.VIEW_FINANCE, event.makerspace_id)
    manager = event_authority.can(actor, event, "manage_registrations")
    from .lifecycle import frozen_policy
    policy = frozen_policy(row)
    if policy.required and policy.missed_action == "block":
        manager = manager and event_authority.can_manage_grants(actor, event)
    prefix = f"/api/v1/admin/events/{event.pk}/stage-responses/{response.pk}" if response else ""
    result.update(response_revision=response.current_submitted_revision.revision if response and response.current_submitted_revision_id else None,
        detail_url=prefix + "/" if organizer and response and response.current_submitted_revision_id else None,
        finance_detail_url=prefix + "/finance/" if finance and response and response.current_submitted_revision_id else None,
        allowed_actions=(["reassign"] if row.state == "cancelled" else ["cancel", "reassign", "extend", "reopen"]) if manager else [])
    return result
