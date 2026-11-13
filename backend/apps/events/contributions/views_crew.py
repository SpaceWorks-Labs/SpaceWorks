"""Crew routes (lane L21a): the staff roster and catering, the member sign-up link, the public section.

Every crew route is web-only until the native event-role authority contract (L21b, #173)
exists; `accounts/programme_route_catalog` records that decision per route.
"""
from django.utils.translation import gettext
import json

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.hackathons.api_base import ProgrammeCommandThrottle, ProgrammeView
from apps.events.hackathons.api_schema import ERRORS
from apps.events.models import Event
from apps.events.serializers_participation import (
    CateringSerializer, CrewAddInput, CrewDecisionInput, CrewOwnSerializer, CrewReorderInput, CrewRowSerializer,
    CrewSignupInput, CrewSignupStateSerializer, CrewUpdateInput, PublicCrewSerializer,
)

from . import crew_reads, crew_workflow
from .models_crew import LIVE, EventCrewMember

TAGS = ["Event crew"]


def masked(request, event, row):
    """A superadmin without an open PII window for this space sees names masked (#114.1)."""
    from apps.accounts.pii_presentation import mask_data, pii_visible
    if not pii_visible(request.user, event.makerspace_id):
        mask_data(row, ("name",))
    return row


class CrewStaffView(ProgrammeView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ProgrammeCommandThrottle]

    def target(self, request, pk):
        event = event_authority.get_event(request.user, pk, "manage_volunteers")
        crew_workflow.require_feature(event)
        return event


class CrewRosterView(CrewStaffView):
    @extend_schema(tags=TAGS, request=None, responses={200: CrewRowSerializer(many=True), **ERRORS},
                   parameters=[OpenApiParameter("kind", str, enum=["organiser", "volunteer", "mentor", "judge"],
                                                description="Filter by crew kind; ignored while `events.crew_kinds` is off.")])
    def get(self, request, pk):
        event = self.target(request, pk)
        rows = crew_reads.roster(event, kind=request.query_params.get("kind"))
        return Response([masked(request, event, crew_reads.project_staff(row)) for row in rows])

    @extend_schema(tags=TAGS, request=CrewAddInput, responses={201: CrewRowSerializer, **ERRORS},
                   summary="Add someone to the crew; they get a free crew place")
    def post(self, request, pk):
        event = self.target(request, pk)
        data = CrewAddInput(data=request.data)
        data.is_valid(raise_exception=True)
        member = get_object_or_404(User, pk=data.validated_data["member_id"], is_active=True)
        crew = crew_workflow.add(event, actor=request.user, member=member, crew_role=data.validated_data["crew_role"],
                                 kind=data.validated_data["kind"])
        return Response(masked(request, event, crew_reads.project_staff(crew)), status=201)


class CrewDecisionView(CrewStaffView):
    @extend_schema(tags=TAGS, request=CrewDecisionInput, responses={200: CrewRowSerializer, **ERRORS})
    def post(self, request, pk, crew_id):
        event = self.target(request, pk)
        data = CrewDecisionInput(data=request.data)
        data.is_valid(raise_exception=True)
        crew = crew_workflow.decide(event, actor=request.user, crew_id=crew_id, **data.validated_data)
        return Response(masked(request, event, crew_reads.project_staff(crew)))


class CrewDetailView(CrewStaffView):
    http_method_names = ["patch", "options"]

    @extend_schema(tags=TAGS, request=CrewUpdateInput, responses={200: CrewRowSerializer, **ERRORS},
                   summary="Staff edit a crew member's label, kind or public visibility")
    def patch(self, request, pk, crew_id):
        event = self.target(request, pk)
        data = CrewUpdateInput(data=request.data)
        data.is_valid(raise_exception=True)
        crew = crew_workflow.update(event, actor=request.user, crew_id=crew_id, **data.validated_data)
        return Response(masked(request, event, crew_reads.project_staff(crew)))


class CrewReorderView(CrewStaffView):
    @extend_schema(tags=TAGS, request=CrewReorderInput, responses={200: CrewRowSerializer(many=True), **ERRORS},
                   summary="Set the staff order of the crew")
    def post(self, request, pk):
        event = self.target(request, pk)
        data = CrewReorderInput(data=request.data)
        data.is_valid(raise_exception=True)
        crew_workflow.reorder(event, actor=request.user, ids=data.validated_data["ids"])
        return Response([masked(request, event, crew_reads.project_staff(row)) for row in crew_reads.roster(event)])


class CrewRemoveView(CrewStaffView):
    @extend_schema(tags=TAGS, request=None, responses={200: CrewRowSerializer, **ERRORS})
    def post(self, request, pk, crew_id):
        event = self.target(request, pk)
        crew = crew_workflow.end(event, actor=request.user, crew_id=crew_id, own=False)
        return Response(masked(request, event, crew_reads.project_staff(crew)))


class CrewCateringView(CrewStaffView):
    @extend_schema(tags=TAGS, request=None, responses={200: CateringSerializer, **ERRORS},
                   summary="Counts of dietary needs among approved crew; never who has them")
    def get(self, request, pk):
        return Response(crew_reads.catering(self.target(request, pk)))


class CrewSignupView(ProgrammeView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProgrammeCommandThrottle]

    def event(self, pk):
        event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk, status="published")
        crew_workflow.require_feature(event)
        return event

    def state(self, request, event):
        from apps.events.models_participation import EventParticipationSettings
        settings = EventParticipationSettings.for_event(event)
        own = EventCrewMember.objects.filter(event=event, member=request.user).order_by("-pk").first()
        if not settings.crew_signup_open and own is None:
            from apps.events.hackathons.admission_errors import fail
            fail("not_found", gettext("Not found."), status=404)
        return {"event_id": event.pk, "event_title": event.title, "starts_at": event.starts_at,
                "open": settings.crew_signup_open, "approval_required": settings.crew_approval_required,
                "crew": crew_reads.project_own(own) if own else None}

    @extend_schema(tags=TAGS, request=None, responses={200: CrewSignupStateSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(self.state(request, self.event(pk)))

    @extend_schema(tags=TAGS, request=CrewSignupInput, responses={201: CrewSignupStateSerializer, **ERRORS},
                   summary="Sign up for the event's crew through its crew link")
    def post(self, request, pk):
        event = self.event(pk)
        data = CrewSignupInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        crew_workflow.signup(event, actor=request.user, crew_role=values["crew_role"], dietary=values["dietary"],
                             answers=json.dumps({"notes": values["notes"]}), show_publicly=values["show_publicly"])
        return Response(self.state(request, event), status=201)


class CrewWithdrawView(CrewSignupView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=TAGS, request=None, responses={200: CrewSignupStateSerializer, **ERRORS})
    def post(self, request, pk):
        event = self.event(pk)
        crew = get_object_or_404(EventCrewMember, event=event, member=request.user, state__in=LIVE)
        crew_workflow.end(event, actor=request.user, crew_id=crew.pk, own=True)
        return Response(self.state(request, event))


class PublicCrewView(ProgrammeView):
    permission_classes = [AllowAny]

    @extend_schema(auth=[], tags=TAGS, request=None, responses={200: PublicCrewSerializer(many=True), **ERRORS},
                   summary="The event's public crew section: opted-in crew with a public profile only")
    def get(self, request, public_token):
        from apps.makerspaces.platform import feature_enabled
        event = get_object_or_404(Event.objects.select_related("makerspace"), public_token=public_token,
                                  status="published", is_public=True)
        if not feature_enabled(event.makerspace, crew_workflow.FEATURE):
            return Response([])
        return Response(crew_reads.public_crew(event))
