"""Open items A22 (role completeness EB6): one queue of registrations waiting on staff, across events.

Pending approvals and waitlisted places used to be findable only event by event. This read-only list
gathers them for every upcoming event in one space that the reader may manage registrations for
(tenant Event Managers, organizers and per-event grant holders alike, through `event_authority`).
Approving and promoting stay on the existing per-registration routes, which run the registration
services and write their audit rows; nothing changes state here.
"""
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from . import event_authority
from .event_permissions import MANAGE_REGISTRATIONS
from .models import Event, EventRegistration

QUEUE_STATUSES = (EventRegistration.Status.PENDING_APPROVAL.value, EventRegistration.Status.WAITLISTED.value)


class QueueEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    capacity = serializers.IntegerField()


class RegistrationQueueRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=QUEUE_STATUSES)
    created_at = serializers.DateTimeField()
    name = serializers.CharField(help_text="The name given at registration.")
    event = QueueEventSerializer()


class RegistrationQueueResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = RegistrationQueueRowSerializer(many=True)


class _QueuePagination(PageNumberPagination):
    page_size = 24


class EventRegistrationQueueView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin events"], summary="List registrations waiting on staff across events",
        description=("Pending approvals and waitlisted places on upcoming events of one space, oldest first, for "
                     "every event the caller may manage registrations on. `status` narrows to `pending_approval` "
                     "or `waitlisted`; `event` to one event. Approve and promote through the per-registration "
                     "routes. 404 when the caller manages no event registrations in the space."),
        parameters=[OpenApiParameter("status", str, required=False, enum=list(QUEUE_STATUSES)),
                    OpenApiParameter("event", int, required=False), OpenApiParameter("page", int, required=False)],
        request=None,
        responses={200: RegistrationQueueResponseSerializer, **{code: ErrorSerializer for code in (401, 403, 404)}},
    )
    def get(self, request, makerspace_id):
        events = event_authority.events_for(
            request.user, MANAGE_REGISTRATIONS, Event.objects.filter(makerspace_id=makerspace_id))
        # No event to manage here (unknown, foreign or Events-off space) answers 404, never an oracle.
        if not events.exists():
            raise Http404
        statuses = [request.query_params["status"]] if request.query_params.get("status") in QUEUE_STATUSES \
            else list(QUEUE_STATUSES)
        rows = (EventRegistration.objects
                .filter(event__in=events.filter(ends_at__gte=timezone.now()).values("pk"), status__in=statuses)
                .select_related("event").order_by("created_at", "id"))
        if str(request.query_params.get("event", "")).isdigit():
            rows = rows.filter(event_id=int(request.query_params["event"]))
        paginator = _QueuePagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(RegistrationQueueRowSerializer(page, many=True).data)
