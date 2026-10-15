from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.events import services
from apps.events.exceptions import DuplicateRegistration
from apps.events.models import Event, EventCollaborator, EventRegistration
from apps.events.serializers_collaborators import (
    CollaborativeEventRegistrationInputSerializer,
    CollaborativeEventSerializer,
)
from apps.events.serializers_public import PublicEventRegistrationResponseSerializer
from apps.events.throttles import CollaborativeRegistrationThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module, require_module_locked
from apps.makerspaces.member_activity_service import active_membership
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceWaiver
from apps.makerspaces.servability import servable_q, servable_queryset
from apps.presence.guard import MemberPresenceRequired, require_active_member
from .public_ticket_queries import with_public_tickets, ticket_membership_ids
from .collaborative_consent import consent_repair_event_ids


MEMBER_EVENT_ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid event request."),
    403: OpenApiResponse(ErrorSerializer, description="Active membership is required."),
    404: OpenApiResponse(ErrorSerializer, description="Collaborative event not found."),
}


def _active_membership(request, makerspace_id):
    """Membership AND the collaborating space's current waiver.

    `active_membership()` alone does not check the waiver, and collaboration is meant to
    relax exactly one condition -- `is_public` -- so the liability factor must survive. This
    is the same guard the ordinary member registration path uses
    (`views_public.PublicEventRegistrationView`), pointed at the COLLABORATOR: the visiting
    member is one of its members, and it is the space that holds their acceptance.
    """
    membership = active_membership(request.user, makerspace_id)
    if membership is None:
        raise MemberPresenceRequired()
    require_module(membership.makerspace, "events")
    require_active_member(request.user, membership.makerspace)
    return membership


def _collaborative_events(makerspace):
    """Events this space's members may register for through the member surface.

    TWO arms, and the host arm is not an afterthought: without it a partner's members could
    register for A's members-only event while A's OWN members could not, since the public
    listing hides a non-public event and this queryset would exclude events A hosts. The
    asymmetry would be absurd -- the space that created the event being the one space unable
    to see it.
    """
    return servable_queryset(Event.objects.filter(
        Q(makerspace=makerspace)
        | Q(
            collaborators__makerspace=makerspace,
            collaborators__status=EventCollaborator.Status.ACCEPTED,
        ) & servable_q("collaborators__makerspace"),
        makerspace__enabled_modules__contains=["events"],
        status=Event.Status.PUBLISHED,
        ends_at__gte=timezone.now(),
    ), relation="makerspace").distinct()


class MemberCollaborativeEventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Member events"],
        summary="List events hosted by accepted collaborators",
        request=None,
        responses={
            200: CollaborativeEventSerializer(many=True),
            **MEMBER_EVENT_ERRORS,
        },
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        membership = _active_membership(request, makerspace_id)
        events = (
            _collaborative_events(membership.makerspace)
            .select_related("makerspace__payment_settings", "series", "category")
            .prefetch_related("organizers__organization")
            .annotate(
                confirmed_count=Count(
                    "registrations",
                    filter=Q(
                        registrations__status__in=(
                            EventRegistration.Status.REGISTERED,
                            EventRegistration.Status.ATTENDED,
                        )
                    ),
                )
            )
            .order_by("starts_at", "id")
        )
        events = list(with_public_tickets(events))
        # One query for every host's active waiver, instead of one per event.
        active_waivers = {
            waiver.makerspace_id: waiver
            for waiver in MakerspaceWaiver.objects.filter(
                makerspace_id__in={event.makerspace_id for event in events},
                is_active=True,
            )
        }
        return Response(
            CollaborativeEventSerializer(
                events, many=True, context={"active_host_waivers": active_waivers, "request": request,
                                           "consent_repair_event_ids": consent_repair_event_ids(events, request.user, active_waivers),
                                           "ticket_membership_ids": ticket_membership_ids(request.user, events)},
            ).data
        )


from .host_waivers import stamp_host_waiver as _stamp_host_waiver


class MemberCollaborativeEventRegistrationView(APIView):
    permission_classes = [IsAuthenticated]
    # Scope selection lives in the throttle itself -- see CollaborativeRegistrationThrottle
    # for why a repair retry must not share the create budget, and why a CANCELLED row is
    # not a retry.
    throttle_classes = [CollaborativeRegistrationThrottle]

    @extend_schema(
        tags=["Member events"],
        summary="Register for a collaborative event",
        request=CollaborativeEventRegistrationInputSerializer,
        responses={
            201: PublicEventRegistrationResponseSerializer,
            **MEMBER_EVENT_ERRORS,
            409: OpenApiResponse(ErrorSerializer, description="Event state conflict."),
            # Registration only -- the list view carries no throttle.
            429: OpenApiResponse(ErrorSerializer, description="Rate limit exceeded."),
        },
    )
    def post(self, request, makerspace_id, pk, *args, **kwargs):
        membership = _active_membership(request, makerspace_id)
        event = get_object_or_404(
            _collaborative_events(membership.makerspace).select_related("makerspace"),
            pk=pk,
        )
        serializer = CollaborativeEventRegistrationInputSerializer(
            data=request.data,
            context={"event": event, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        registration_data = serializer.validated_data.copy()
        with transaction.atomic():
            locked_event = Event.objects.select_for_update(of=("self",)).get(pk=event.pk)
            from .organization_audience import lock_admission_sources
            lock_admission_sources(locked_event, [request.user.pk], extra_space_ids=[membership.makerspace_id])
            # The view's collaboration check is unlocked and can go stale. Re-read it
            # under the event lock used by every collaboration mutation before register()
            # takes its own nested locks, so removal cannot race registration creation.
            collaboration = servable_queryset(
                EventCollaborator.objects.filter(
                    event=locked_event,
                    makerspace=membership.makerspace,
                    status=EventCollaborator.Status.ACCEPTED,
                ),
                relation="makerspace",
            )
            collaboration = collaboration.select_related("makerspace").first()
            if collaboration is None and locked_event.makerspace_id != membership.makerspace_id:
                raise NotFound()
            # The COLLABORATOR's module gate must be re-checked under ITS row lock too.
            # `register()` locks only the host, so an unlocked read here leaves the window
            # every `require_module_locked` call site exists to close: the partner
            # uninstalls `events` and purges it, and this insert then writes provenance
            # pointing at the partner *after* an irreversible purge cleared exactly those
            # rows. Event lock first, then makerspace, matching `publish()`.
            via = collaboration.makerspace if collaboration else membership.makerspace
            # Lock the host and the collaborator TOGETHER in primary-key order. Locking only
            # `via` here and letting `register()` take the host afterwards deadlocks on
            # reciprocal collaborations: an A-hosted event via B takes B then A, while a
            # B-hosted event via A takes A then B, and the two event locks are different rows
            # so Postgres has to abort one.
            list(
                Makerspace.objects.select_for_update()
                .filter(pk__in={locked_event.makerspace_id, via.pk})
                .order_by("pk")
            )
            require_module_locked(via.pk, "events")
            # And the membership + waiver, re-read under the collaborator's now-held row
            # lock. `_active_membership` ran unlocked at the top of the request, so a
            # revocation or a new waiver version committed since then would otherwise
            # still produce a registration -- eligibility has to be as transactional as
            # the module gate beside it.
            MakerspaceMembership.objects.select_for_update().filter(
                makerspace_id=via.pk, user=request.user,
            ).first()
            require_active_member(request.user, via)
            try:
                registration = services.register(
                    locked_event,
                    member=request.user,
                    actor=request.user,
                    collaborative=True, repair_duplicate=True,
                    via_makerspace=via,
                    **registration_data,
                )
            except DuplicateRegistration:
                # A lost response or a double-submit must not report failure for a
                # registration that exists. Report the status of the row the caller ACTUALLY
                # owns, not `exc.fresh_status` -- that is the status a *new* registration
                # would receive, so once the event filled it would tell a confirmed member
                # they are waitlisted.
                owned_row = EventRegistration.objects.filter(
                    event=locked_event, member=request.user,
                ).first()
                return Response(
                    {"status": owned_row.status if owned_row else None},
                    status=status.HTTP_201_CREATED,
                )
        return Response(
            PublicEventRegistrationResponseSerializer(registration).data,
            status=status.HTTP_201_CREATED,
        )
