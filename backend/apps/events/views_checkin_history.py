"""Who has checked in: a minimal attendance list a check-in-only grantee may read."""

from django.db.models import F, OuterRef, Subquery
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from .event_permissions import CHECK_IN
from .models import EventCheckInEvent, EventRegistration
from .views_admin_event_detail import _manageable_event

# The scanner UI speaks of "QR", "manual" and "offline"; the evidence rows keep their
# finer-grained source. Station and legacy rows have no person behind them.
SOURCE_LABELS = {
    EventCheckInEvent.Source.QR: "qr",
    EventCheckInEvent.Source.ONLINE: "manual",
    EventCheckInEvent.Source.OFFLINE_SYNC: "offline",
    EventCheckInEvent.Source.VENUE_STATION: "station",
    EventCheckInEvent.Source.LEGACY: "legacy",
}


class EventCheckInRowSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField(source="pk")
    attendee_name = serializers.CharField(source="name")
    ticket_type = serializers.CharField(source="ticket_type.name", allow_null=True, default=None)
    attended_at = serializers.DateTimeField(source="checked_in_at", allow_null=True)
    source = serializers.ChoiceField(choices=sorted(set(SOURCE_LABELS.values())))
    checked_in_by = serializers.CharField(allow_null=True)


class EventCheckInPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = EventCheckInRowSerializer(many=True)


class _CheckInPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 200


def checked_in(event):
    # event_checkin_history_idx (registration, attended_at) serves the latest-row lookup.
    latest = EventCheckInEvent.objects.filter(registration=OuterRef("pk")).order_by("-attended_at", "-id")
    return (
        EventRegistration.objects.filter(event=event, status=EventRegistration.Status.ATTENDED)
        .select_related("ticket_type")
        .annotate(
            checked_in_at=Subquery(latest.values("attended_at")[:1]),
            checkin_source=Subquery(latest.values("source")[:1]),
            checkin_actor_id=Subquery(latest.values("actor_id")[:1]),
        )
        .order_by(F("checked_in_at").desc(nulls_last=True), "-pk")
    )


def _actor_names(rows):
    ids = {row.checkin_actor_id for row in rows if row.checkin_actor_id}
    return {user.pk: user.display_name or user.username
            for user in User.objects.filter(pk__in=ids).only("pk", "display_name", "username")}


class EventCheckInHistoryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin events"],
        summary="List who has checked in to an event",
        description=("Newest first. Needs only the check_in event permission, so a door volunteer "
                     "or speaker with a check-in grant can see the list beside the scanner. "
                     "Carries names only: no email, phone, payment or custom answers."),
        parameters=[OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY),
                    OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY)],
        request=None,
        responses={200: EventCheckInPageSerializer, **{code: ErrorSerializer for code in (401, 403, 404)}},
    )
    def get(self, request, pk):
        event = _manageable_event(request.user, pk, CHECK_IN)
        paginator = _CheckInPagination()
        rows = paginator.paginate_queryset(checked_in(event), request, view=self)
        names = _actor_names(rows)
        for row in rows:
            row.source = SOURCE_LABELS.get(row.checkin_source, "legacy")
            row.checked_in_by = names.get(row.checkin_actor_id)
        return paginator.get_paginated_response(EventCheckInRowSerializer(rows, many=True).data)
