from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from .api_common import ProgrammeView, paginated, page_schema
from .models_roles import EventRolePosting, EventRoleAssignment
from .models_shifts import EventShift, EventShiftSignup
from .ports import ports
from . import projections, role_workflow, shift_workflow, attendance_workflow
from .serializers import (RoleInputSerializer, RoleSerializer, PostingSerializer, SignupSerializer,
    ShiftSerializer, ShiftApplySerializer, CommandSerializer, DateReviewSerializer, ReasonCommandSerializer, ERRORS)


class PostingListView(ProgrammeView):
    feature = None

    @extend_schema(responses={200: page_schema("MemberRolePostingPage", PostingSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        ids = ports().visible_posting_ids(actor_id=request.user.pk, event_id=pk)
        rows = EventRolePosting.objects.filter(event_id=pk, pk__in=ids).order_by("pk")
        return paginated(request, rows, projections.posting)


class PostingDetailView(PostingListView):
    @extend_schema(responses={200: PostingSerializer, **ERRORS})
    def get(self, request, pk, makerspace_id, posting_id):
        self.event(request, pk, makerspace_id)
        ports().require_role_audience(actor_id=request.user.pk, event_id=pk, posting_id=posting_id)
        row = get_object_or_404(EventRolePosting, event_id=pk, pk=posting_id)
        return Response(projections.posting(row, actor=request.user, detail=True))


class RoleApplicationCreateView(PostingListView):
    http_method_names = ["post", "options"]
    @extend_schema(request=RoleInputSerializer, responses={201: RoleSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, posting_id):
        self.event(request, pk, makerspace_id)
        result = role_workflow.apply(actor=request.user, event_id=pk, posting_id=posting_id,
                                     payload=self.input(request, RoleInputSerializer))
        return Response(projections.role(result.row, detail=True, owner=True), status=result.status)


class RoleApplicationListView(PostingListView):
    @extend_schema(responses={200: page_schema("MemberRoleApplicationPage", RoleSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        rows = EventRoleAssignment.objects.filter(event_id=pk, member=request.user).order_by("pk")
        return paginated(request, rows, lambda row: projections.role(row, owner=True))


class RoleApplicationDetailView(RoleApplicationListView):
    @extend_schema(responses={200: RoleSerializer, **ERRORS})
    def get(self, request, pk, makerspace_id, assignment_id):
        self.event(request, pk, makerspace_id)
        row = get_object_or_404(EventRoleAssignment, event_id=pk, pk=assignment_id, member=request.user)
        return Response(projections.role(row, detail=True, owner=True))

    @extend_schema(request=RoleInputSerializer, responses={200: RoleSerializer, **ERRORS})
    def patch(self, request, pk, makerspace_id, assignment_id):
        self.event(request, pk, makerspace_id)
        result = role_workflow.edit(actor=request.user, event_id=pk, assignment_id=assignment_id,
                                    payload=self.input(request, RoleInputSerializer))
        return Response(projections.role(result.row, detail=True, owner=True), status=result.status)


class RoleSubmitView(RoleApplicationListView):
    http_method_names = ["post", "options"]
    @extend_schema(request=RoleInputSerializer, responses={200: RoleSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, assignment_id):
        self.event(request, pk, makerspace_id)
        result = role_workflow.edit(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, RoleInputSerializer), submit=True)
        return Response(projections.role(result.row, detail=True, owner=True), status=result.status)


class RoleWithdrawView(RoleApplicationListView):
    http_method_names = ["post", "options"]
    @extend_schema(request=ReasonCommandSerializer, responses={200: RoleSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, assignment_id):
        self.event(request, pk, makerspace_id)
        result = role_workflow.transition(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, ReasonCommandSerializer), action="withdraw")
        return Response(projections.role(result.row, owner=True))


class RoleDateReviewView(RoleApplicationListView):
    http_method_names = ["post", "options"]
    @extend_schema(request=DateReviewSerializer, responses={200: RoleSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, assignment_id):
        self.event(request, pk, makerspace_id)
        result = role_workflow.transition(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, DateReviewSerializer), action="date_review")
        return Response(projections.role(result.row, owner=True, detail=True))


class ShiftListView(ProgrammeView):
    feature = "events.volunteering"

    @extend_schema(responses={200: page_schema("MemberVolunteerShiftPage", ShiftSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        ids = ports().visible_posting_ids(actor_id=request.user.pk, event_id=pk)
        rows = EventShift.objects.filter(event_id=pk, posting_id__in=ids, kind="volunteer").order_by("starts_at", "pk")
        return paginated(request, rows, lambda row: projections.shift(row, actor=request.user))


class ShiftApplyView(ShiftListView):
    http_method_names = ["post", "options"]
    @extend_schema(request=ShiftApplySerializer, responses={201: SignupSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, shift_id):
        self.event(request, pk, makerspace_id)
        result = shift_workflow.apply(actor=request.user, event_id=pk, shift_id=shift_id,
                                      payload=self.input(request, ShiftApplySerializer))
        return Response(projections.signup(result.row), status=result.status)


class SignupListView(ShiftListView):
    @extend_schema(responses={200: page_schema("MemberShiftSignupPage", SignupSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        return paginated(request, EventShiftSignup.objects.filter(event_id=pk, member=request.user).order_by("pk"), projections.signup)


class SignupDetailView(SignupListView):
    @extend_schema(responses={200: SignupSerializer, **ERRORS})
    def get(self, request, pk, makerspace_id, signup_id):
        self.event(request, pk, makerspace_id)
        return Response(projections.signup(get_object_or_404(EventShiftSignup,
            event_id=pk, pk=signup_id, member=request.user)))


class SignupWithdrawView(SignupListView):
    http_method_names = ["post", "options"]
    @extend_schema(request=CommandSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, signup_id):
        self.event(request, pk, makerspace_id)
        result = shift_workflow.transition(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, CommandSerializer), action="withdraw")
        return Response(projections.signup(result.row))


class SignupCheckInView(SignupListView):
    http_method_names = ["post", "options"]
    action = "check_in"

    @extend_schema(request=CommandSerializer, responses={200: SignupSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, signup_id):
        self.event(request, pk, makerspace_id)
        result = attendance_workflow.command(actor=request.user, event_id=pk, signup_id=signup_id,
            payload=self.input(request, CommandSerializer), action=self.action)
        return Response(projections.signup(result.row))


class SignupCheckOutView(SignupCheckInView):
    action = "check_out"
