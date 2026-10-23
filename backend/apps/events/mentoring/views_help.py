from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.admin_api.permissions import IsActiveStaff
from apps.events.contributions.api_common import ProgrammeView, page_schema, paginated
from apps.events.contributions.serializers import CommandSerializer, ReasonCommandSerializer, ERRORS
from apps.events.contributions.ports import ports
from .models_queue import EventHelpRequest
from . import help_workflow, policy, projections
from .serializers import (HelpCreateSerializer, HelpSerializer, CommentInputSerializer, CommentSerializer,
                          ResolveInputSerializer, ReopenInputSerializer, AssignHelpSerializer)


class HelpCollectionView(ProgrammeView):
    @extend_schema(responses={200: page_schema("MemberHelpPage", HelpSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id=None):
        event = self.event(request, pk, makerspace_id)
        rows = EventHelpRequest.objects.filter(event=event, practice_run_id__isnull=True).select_related("type").order_by("-priority", "created_at", "pk")
        if not self.admin:
            ids = ports().teams.own_ids(actor_id=request.user.pk, event_id=pk)
            rows = rows.filter(team_id__in=ids)
        elif not policy.queue_manager(request.user, event):
            mentor, profile = policy.mentor_for(request.user, event)
            ids = [row.pk for row in rows if row.claimed_by_id == mentor.pk or (
                row.state == "open" and policy.visit_eligible(assignment=mentor, profile=profile,
                    team_id=row.team_id, skill_tags=row.type.skill_tags, priority_until=row.exclusive_until))]
            rows = rows.filter(pk__in=ids)
        return paginated(request, rows, lambda row: projections.help_request(row, actor=request.user,
            event=event, member=not self.admin))

    @extend_schema(request=HelpCreateSerializer, responses={201: HelpSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id=None):
        event = self.event(request, pk, makerspace_id)
        result = help_workflow.create(actor=request.user, event_id=pk,
            payload=self.input(request, HelpCreateSerializer), mentor_origin=self.admin)
        return Response(projections.help_request(result.row, actor=request.user, event=event,
            member=not self.admin), status=result.status)


class AdminHelpCollectionView(HelpCollectionView):
    admin = True
    permission_classes = [IsActiveStaff]


class HelpDetailView(ProgrammeView):
    def target(self, request, pk, help_id, makerspace_id=None):
        event = self.event(request, pk, makerspace_id)
        row = get_object_or_404(EventHelpRequest, pk=help_id, event=event)
        help_workflow._detail_access(request.user, event, row, member_surface=not self.admin)
        return event, row

    @extend_schema(responses={200: HelpSerializer, **ERRORS})
    def get(self, request, pk, help_id, makerspace_id=None):
        event, row = self.target(request, pk, help_id, makerspace_id)
        return Response(projections.help_request(row, actor=request.user, event=event,
            detail=True, member=not self.admin))


class AdminHelpDetailView(HelpDetailView):
    admin = True
    permission_classes = [IsActiveStaff]


class HelpCommentsView(HelpDetailView):
    @extend_schema(responses={200: page_schema("HelpCommentPage", CommentSerializer), **ERRORS})
    def get(self, request, pk, help_id, makerspace_id=None):
        _, row = self.target(request, pk, help_id, makerspace_id)
        return paginated(request, row.comments.select_related("request").order_by("created_at", "pk"), projections.comment)

    @extend_schema(request=CommentInputSerializer, responses={201: CommentSerializer, **ERRORS})
    def post(self, request, pk, help_id, makerspace_id=None):
        self.target(request, pk, help_id, makerspace_id)
        result = help_workflow.comment(actor=request.user, event_id=pk, help_id=help_id,
            payload=self.input(request, CommentInputSerializer), member_surface=not self.admin)
        return Response(projections.comment(result.row), status=result.status)


class AdminHelpCommentsView(HelpCommentsView):
    admin = True
    permission_classes = [IsActiveStaff]


class HelpCommandView(ProgrammeView):
    action = "cancel"
    serializer = CommandSerializer

    def execute(self, request, pk, help_id, makerspace_id=None):
        event = self.event(request, pk, makerspace_id)
        result = help_workflow.command(actor=request.user, event_id=pk, help_id=help_id,
            payload=self.input(request, self.serializer), action=self.action, member_surface=not self.admin)
        data = projections.help_request(result.row, actor=request.user, event=event, member=not self.admin)
        if self.action == "cancel":
            data["claim_released"] = True
        return Response(data)


class HelpCancelView(HelpCommandView):
    serializer = ReasonCommandSerializer

    @extend_schema(request=ReasonCommandSerializer, responses={200: HelpSerializer, **ERRORS})
    def post(self, request, pk, help_id, makerspace_id):
        return self.execute(request, pk, help_id, makerspace_id)


class HelpReopenView(HelpCommandView):
    action = "reopen"
    serializer = ReopenInputSerializer

    @extend_schema(request=ReopenInputSerializer, responses={200: HelpSerializer, **ERRORS})
    def post(self, request, pk, help_id, makerspace_id=None):
        return self.execute(request, pk, help_id, makerspace_id)


class AdminHelpClaimView(HelpCommandView):
    admin = True
    action = "claim"
    permission_classes = [IsActiveStaff]

    @extend_schema(request=CommandSerializer, responses={200: HelpSerializer, **ERRORS})
    def post(self, request, pk, help_id):
        return self.execute(request, pk, help_id)


class AdminHelpReleaseView(AdminHelpClaimView):
    action = "release"


class AdminHelpResolveView(AdminHelpClaimView):
    action = "resolve"
    serializer = ResolveInputSerializer

    @extend_schema(request=ResolveInputSerializer, responses={200: HelpSerializer, **ERRORS})
    def post(self, request, pk, help_id):
        return self.execute(request, pk, help_id)


class AdminHelpReopenView(HelpReopenView):
    admin = True
    permission_classes = [IsActiveStaff]


class AdminHelpAssignView(AdminHelpClaimView):
    action = "assign"
    serializer = AssignHelpSerializer

    @extend_schema(request=AssignHelpSerializer, responses={200: HelpSerializer, **ERRORS})
    def post(self, request, pk, help_id):
        return self.execute(request, pk, help_id)
