from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from .api_common import AdminView, paginated, page_schema
from .models_roles import EventRoleAssignment, EventRolePosting
from .models_shifts import EventShift, EventShiftSignup
from . import projections, management_workflow, role_workflow, shift_workflow, attendance_workflow
from .serializers import (RoleSerializer, AdminPostingSerializer, ShiftSerializer, SignupSerializer, AdminShiftSerializer,
                          CommandSerializer, HoursAdjustSerializer, ERRORS)
from .serializers_management import (AdminRoleSerializer, PostingWriteSerializer, ShiftWriteSerializer,
                                     AdminAttendanceSerializer)


class RolesView(AdminView):
    permission = "manage_team"
    feature = None

    @extend_schema(responses={200: page_schema("AdminEventRolesPage", RoleSerializer), **ERRORS})
    def get(self, request, pk):
        self.event(request, pk)
        return paginated(request, EventRoleAssignment.objects.filter(event_id=pk).order_by("pk"), projections.role)

    @extend_schema(request=AdminRoleSerializer, responses={201: RoleSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = management_workflow.save_role(actor=request.user, event_id=pk,
            payload=self.input(request, AdminRoleSerializer))
        return Response(projections.role(result.row), status=result.status)


class RoleDetailView(RolesView):
    http_method_names = ["get", "patch", "head", "options"]
    @extend_schema(responses={200: RoleSerializer, **ERRORS})
    def get(self, request, pk, assignment_id):
        event = self.event(request, pk)
        from apps.events import event_authority
        return Response(projections.role(get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=pk),
            detail=event_authority.can(request.user, event, None), actor=request.user))

    @extend_schema(request=AdminRoleSerializer, responses={200: RoleSerializer, **ERRORS})
    def patch(self, request, pk, assignment_id):
        self.event(request, pk)
        result = management_workflow.save_role(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, AdminRoleSerializer))
        return Response(projections.role(result.row))


class RoleApproveView(RolesView):
    http_method_names = ["post", "options"]
    action = "approve"

    @extend_schema(request=CommandSerializer, responses={200: RoleSerializer, **ERRORS})
    def post(self, request, pk, assignment_id):
        self.event(request, pk)
        result = role_workflow.transition(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, CommandSerializer), action=self.action)
        return Response(projections.role(result.row))


class RoleRevokeView(RoleApproveView):
    action = "revoke"


class PostingsView(AdminView):
    permission = "view"
    feature = None

    @extend_schema(responses={200: page_schema("AdminEventPostingPage", AdminPostingSerializer), **ERRORS})
    def get(self, request, pk):
        event = self.event(request, pk)
        from apps.events import event_authority
        roles = []
        if event_authority.can(request.user, event, "manage_volunteers"):
            roles.append("volunteer")
        if event_authority.can(request.user, event, "manage_team"):
            roles.append("mentor")
        return paginated(request, EventRolePosting.objects.filter(event_id=pk, role__in=roles).order_by("pk"), projections.admin_posting)

    @extend_schema(request=PostingWriteSerializer, responses={201: AdminPostingSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = management_workflow.save_posting(actor=request.user, event_id=pk,
            payload=self.input(request, PostingWriteSerializer))
        return Response(projections.admin_posting(result.row), status=result.status)


class PostingDetailView(PostingsView):
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: AdminPostingSerializer, **ERRORS})
    def get(self, request, pk, posting_id):
        event = self.event(request, pk)
        row = get_object_or_404(EventRolePosting, pk=posting_id, event_id=pk)
        from apps.events import event_authority
        event_authority.require(request.user, event, "manage_team" if row.role == "mentor" else "manage_volunteers")
        return Response(projections.admin_posting(row))

    @extend_schema(request=PostingWriteSerializer, responses={200: AdminPostingSerializer, **ERRORS})
    def patch(self, request, pk, posting_id):
        self.event(request, pk)
        result = management_workflow.save_posting(actor=request.user, event_id=pk, posting_id=posting_id,
            payload=self.input(request, PostingWriteSerializer))
        return Response(projections.admin_posting(result.row))


class ShiftsView(AdminView):
    permission = "view"
    feature = None

    @extend_schema(responses={200: page_schema("AdminEventShiftPage", ShiftSerializer), **ERRORS})
    def get(self, request, pk):
        event = self.event(request, pk)
        from apps.events import event_authority
        kinds = []
        if event_authority.can(request.user, event, "manage_volunteers"):
            kinds.append("volunteer")
        if event_authority.can(request.user, event, "manage_team"):
            kinds.append("office_hours")
        return paginated(request, EventShift.objects.filter(event_id=pk, kind__in=kinds).order_by("starts_at", "pk"), projections.shift)

    @extend_schema(request=ShiftWriteSerializer, responses={201: ShiftSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = management_workflow.save_shift(actor=request.user, event_id=pk,
            payload=self.input(request, ShiftWriteSerializer))
        return Response(projections.shift(result.row), status=result.status)


class ShiftDetailView(ShiftsView):
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: AdminShiftSerializer, **ERRORS})
    def get(self, request, pk, shift_id):
        event = self.event(request, pk)
        row = get_object_or_404(EventShift, pk=shift_id, event_id=pk)
        from apps.events import event_authority
        event_authority.require(request.user, event, "manage_team" if row.kind == "office_hours" else "manage_volunteers")
        return Response(projections.admin_shift(row, request.user))

    @extend_schema(request=ShiftWriteSerializer, responses={200: ShiftSerializer, **ERRORS})
    def patch(self, request, pk, shift_id):
        self.event(request, pk)
        result = management_workflow.save_shift(actor=request.user, event_id=pk, shift_id=shift_id,
            payload=self.input(request, ShiftWriteSerializer))
        return Response(projections.shift(result.row))


class SignupApproveView(AdminView):
    http_method_names = ["post", "options"]
    permission = "manage_volunteers"
    feature = "events.volunteering"

    @extend_schema(request=CommandSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, signup_id):
        self.event(request, pk)
        result = shift_workflow.transition(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, CommandSerializer), action="approve")
        return Response(projections.signup(result.row, owner=False))


class SignupWithdrawView(SignupApproveView):
    @extend_schema(request=CommandSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, signup_id):
        self.event(request, pk)
        result = shift_workflow.transition(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, CommandSerializer), action="withdraw", staff=True)
        return Response(projections.signup(result.row, owner=False))


class SignupAttendanceView(SignupApproveView):
    action = "check_in"

    @extend_schema(request=AdminAttendanceSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, signup_id):
        self.event(request, pk)
        result = attendance_workflow.command(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, AdminAttendanceSerializer), action=self.action, staff=True)
        return Response(projections.signup(result.row, owner=False))


class SignupCheckOutView(SignupAttendanceView):
    action = "check_out"


class SignupVerifyHoursView(SignupAttendanceView):
    action = "verify_hours"

    @extend_schema(request=CommandSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, signup_id):
        self.event(request, pk)
        result = attendance_workflow.command(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, CommandSerializer), action=self.action, staff=True)
        return Response(projections.signup(result.row, owner=False))


class SignupNoShowView(SignupAttendanceView):
    action = "no_show"


class SignupAdjustHoursView(SignupAttendanceView):
    @extend_schema(request=HoursAdjustSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, signup_id):
        self.event(request, pk)
        result = attendance_workflow.command(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, HoursAdjustSerializer), action="adjust_hours", staff=True)
        return Response(projections.signup(result.row, owner=False))
