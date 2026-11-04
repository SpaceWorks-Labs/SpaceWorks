"""Speaker identity routes: staff assign/invite/remove/search, and the member claim."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from . import speaker_identity as speakers
from .event_permissions import EDIT_DETAILS
from .models import Event, EventSpeaker
from .serializers_admin import EmptyActionSerializer
from .serializers_speakers import (
    EventSpeakerListSerializer, EventSpeakerSerializer, SpeakerAssignInputSerializer,
    SpeakerCandidateListSerializer, SpeakerClaimInputSerializer, SpeakerClaimResponseSerializer,
    SpeakerInviteInputSerializer, SpeakerInviteResponseSerializer,
)
from .throttles import SpeakerClaimThrottle
from .views_admin_event_detail import _manageable_event
from .views_invites import ERRORS, PAGE_PARAMETERS, manageable_event_code, paginated

TAGS = ["Admin events"]


class EventSpeakerListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=PAGE_PARAMETERS, responses={200: EventSpeakerListSerializer, **ERRORS},
                   description="Account-linked speakers of this event, including open claim invitations and "
                               "removed rows. Requires the event's edit_details authority.")
    def get(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        rows = event.speakers.select_related("user", "section").order_by("removed_at", "created_at", "pk")
        return paginated(request, rows, EventSpeakerSerializer)

    @extend_schema(tags=TAGS, request=SpeakerAssignInputSerializer, responses={201: EventSpeakerSerializer, **ERRORS},
                   description="Assign an account from this event's members, staff or registrants as a speaker. "
                               "grant_check_in also creates a check_in staff grant and needs event-manager authority. Audited.")
    def post(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        values = SpeakerAssignInputSerializer(data=request.data)
        values.is_valid(raise_exception=True)
        data = values.validated_data
        row = speakers.assign_speaker(event, actor=request.user, user=data["user_id"], name=data["display_name"],
                                      section_slug=data["section_slug"], grant_check_in=data["grant_check_in"])
        return Response(EventSpeakerSerializer(row).data, status=201)


class EventSpeakerInviteView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=SpeakerInviteInputSerializer, responses={201: SpeakerInviteResponseSerializer, **ERRORS},
                   description="Create a single-use, 14-day speaker claim link. Only its digest is stored; the URL "
                               "is returned once with the bearer in the fragment. Audited.")
    def post(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        values = SpeakerInviteInputSerializer(data=request.data)
        values.is_valid(raise_exception=True)
        data = values.validated_data
        row, url = speakers.invite_speaker(event, actor=request.user, name=data["display_name"],
                                           section_slug=data["section_slug"], grant_check_in=data["grant_check_in"])
        return Response({"speaker": EventSpeakerSerializer(row).data, "claim_url": url}, status=201)


class EventSpeakerRemoveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=EmptyActionSerializer, responses={200: EventSpeakerSerializer, **ERRORS},
                   description="Remove a speaker link or withdraw an unclaimed invitation. Soft and audited; "
                               "any check-in grant stays on the Team tab.")
    def post(self, request, pk):
        row = manageable_event_code(request.user, EventSpeaker.objects.all(), pk, EDIT_DETAILS)
        EmptyActionSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(EventSpeakerSerializer(speakers.remove_speaker(row, actor=request.user)).data)


class EventSpeakerCandidateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, parameters=[OpenApiParameter("search", str, OpenApiParameter.QUERY)],
                   responses={200: SpeakerCandidateListSerializer, **ERRORS},
                   description="At most 20 active accounts within the event's scope (this space's members and staff, "
                               "and this event's registrants) matching name or username. Needs at least 2 characters.")
    def get(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        accounts = list(speakers.candidate_accounts(event, request.query_params.get("search"))[:20])
        member_ids = set(event.makerspace.memberships.filter(user__in=accounts, status="active")
                         .values_list("user_id", flat=True))
        staff_ids = set(event.eventstaffgrant_rows.filter(user__in=accounts, revoked_at__isnull=True)
                        .values_list("user_id", flat=True))
        results = [{"id": user.pk, "display_name": speakers.display_name(user), "username": user.username,
                    "relation": "member" if user.pk in member_ids else "staff" if user.pk in staff_ids else "registrant"}
                   for user in accounts]
        return Response({"results": results})


class MemberSpeakerClaimView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SpeakerClaimThrottle]

    @extend_schema(tags=["Member events"], request=SpeakerClaimInputSerializer,
                   responses={200: SpeakerClaimResponseSerializer, **ERRORS},
                   description="Claim a speaker invitation for the signed-in account. Unknown, expired, used and "
                               "withdrawn links are all a uniform 404. Audited with the claimant as actor.")
    def post(self, request):
        values = SpeakerClaimInputSerializer(data=request.data)
        values.is_valid(raise_exception=True)
        row = speakers.claim_speaker(values.validated_data["token"], actor=request.user)
        event = get_object_or_404(Event, pk=row.event_id)
        return Response({"speaker_id": row.pk, "display_name": row.display_name,
                         "event": {"id": event.pk, "title": event.title, "starts_at": event.starts_at,
                                   "ends_at": event.ends_at}})
