"""C2 command views; G must ratify and register urls_completion before mounting."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiTypes
from rest_framework import serializers
from rest_framework.response import Response
from .api_common import AdminView, ProgrammeView, envelope
from .serializers import CommandSerializer, RoleSerializer, AggregateSerializer, ERRORS
from . import role_workflow, projections, requirements_workflow, admission_adapter
from .models_roles import EventRoleAssignment


class RoleReasonSerializer(CommandSerializer):
    reason = serializers.CharField(max_length=2000)


class AdmissionSerializer(CommandSerializer):
    ticket_type_id = serializers.IntegerField(min_value=1)
    capacity_policy = serializers.ChoiceField(choices=["event_capacity", "reserved_contributor_capacity"])


class AdmissionResultSerializer(AggregateSerializer):
    assignment_id = serializers.IntegerField()
    registration_id = serializers.IntegerField()
    capacity_policy = serializers.CharField()


class RoleCompletionView(AdminView):
    permission = "view"
    feature = None
    action = "complete"
    http_method_names = ["post", "options"]

    @extend_schema(request=RoleReasonSerializer, responses={200: RoleSerializer, **ERRORS})
    def post(self, request, pk, assignment_id):
        self.event(request, pk)
        result = role_workflow.transition(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, RoleReasonSerializer), action=self.action)
        return Response(projections.role(result.row))


class RoleRejectView(RoleCompletionView):
    action = "reject"


class RoleReopenView(RoleCompletionView):
    action = "reopen_answers"


class RoleReconfirmView(RoleCompletionView):
    action = "reconfirm"


class RoleDeclineView(ProgrammeView):
    feature = None
    http_method_names = ["post", "options"]

    @extend_schema(request=RoleReasonSerializer, responses={200: RoleSerializer, **ERRORS})
    def post(self, request, pk, assignment_id, makerspace_id):
        self.event(request, pk, makerspace_id)
        result = role_workflow.transition(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, RoleReasonSerializer), action="decline")
        return Response(projections.role(result.row, owner=True))


class RoleOwnerExportView(ProgrammeView):
    feature = None

    @extend_schema(responses={200: OpenApiTypes.OBJECT, **ERRORS})
    def get(self, request, pk, assignment_id, makerspace_id):
        self.event(request, pk, makerspace_id)
        from apps.events.mentoring.import_export import export_role_owner
        row = get_object_or_404(EventRoleAssignment, event_id=pk, pk=assignment_id, member=request.user)
        return Response(export_role_owner(actor=request.user, row=row))


class RequirementOverrideView(AdminView):
    feature = None
    permission = "view"

    @extend_schema(request=requirements_workflow.RequirementOverrideSerializer,
                   responses={201: AggregateSerializer, **ERRORS})
    def post(self, request, pk, assignment_id):
        self.event(request, pk)
        result = requirements_workflow.override(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, requirements_workflow.RequirementOverrideSerializer))
        return Response({**envelope(result.row), "state": "recorded"}, status=result.status)


class ContributorAdmissionView(AdminView):
    permission = None
    feature = None

    @extend_schema(request=AdmissionSerializer, responses={201: AdmissionResultSerializer, **ERRORS})
    def post(self, request, pk, assignment_id):
        self.event(request, pk)
        result = admission_adapter.admit(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, AdmissionSerializer))
        row = result.row
        return Response({**envelope(row), "state": "admitted", "registration_id": row.registration_id,
            "assignment_id": row.assignment_id, "capacity_policy": row.capacity_policy}, status=result.status)
