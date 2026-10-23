"""Deduplicated, occurrence-authorized series guests without a global contact directory."""

import logging

from django.db.models import Case, F, IntegerField, Max, Q, Value, When
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.event_permissions import CHECK_IN, MANAGE_REGISTRATIONS, VIEW
from apps.events.models import Event, EventRegistration

from .serializers import ERRORS
from .providers import answer_projector

logger = logging.getLogger(__name__)


class GuestFilter(serializers.Serializer):
    event_id = serializers.IntegerField(min_value=1, required=False)
    status = serializers.ChoiceField(choices=EventRegistration.Status.choices, required=False)
    attendance = serializers.ChoiceField(choices=("attended", "not_attended"), required=False)
    page = serializers.IntegerField(min_value=1, required=False)


class GuestOccurrenceSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    registration_id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    attended_at = serializers.DateTimeField(allow_null=True)
    email = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    custom_answers = serializers.JSONField(required=False, allow_null=True)
    custom_answers_unavailable_reason = serializers.CharField(required=False)


class SeriesGuestSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(allow_null=True)
    registration_id = serializers.IntegerField(allow_null=True)
    occurrences = GuestOccurrenceSerializer(many=True)


class SeriesGuestsPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SeriesGuestSerializer(many=True)


def authorized_registrations(series, actor, filters):
    base = Event.objects.filter(series=series, makerspace_id=series.makerspace_id)
    manageable = event_authority.events_for(actor, MANAGE_REGISTRATIONS, base)
    checkable = event_authority.events_for(actor, CHECK_IN, base)
    events = base.filter(Q(pk__in=manageable.values("pk")) | Q(pk__in=checkable.values("pk")))
    if "event_id" in filters:
        events = events.filter(pk=filters["event_id"])
    if events.count() > 200:
        raise ValidationError({"event_id": "Choose an occurrence for a series with over 200 authorized occurrences."})
    rows = EventRegistration.objects.filter(event__in=events)
    if "status" in filters:
        rows = rows.filter(status=filters["status"])
    if filters.get("attendance") == "attended":
        rows = rows.filter(status="attended")
    elif filters.get("attendance") == "not_attended":
        rows = rows.exclude(status="attended")
    return rows


def project_guests(rows, identities, *, actor):
    selected = Q(pk__in=[])
    for identity in identities:
        selected |= Q(member_id=identity["member_id"]) if identity["member_id"] is not None else Q(pk=identity["registration_id"])
    details = rows.filter(selected).select_related("event__makerspace", "event__series").annotate(
        latest_attended_at=Max("check_in_events__attended_at")).order_by("event__starts_at", "pk")
    grouped = {(row["member_id"], row["registration_id"]): {**row, "occurrences": []} for row in identities}
    for row in details:
        key = (row.member_id, None if row.member_id is not None else row.pk)
        # Recheck each occurrence at the individual projection boundary as well.
        manages = event_authority.can(actor, row.event, MANAGE_REGISTRATIONS)
        if not manages and not event_authority.can(actor, row.event, CHECK_IN):
            continue
        value = {"event_id": row.event_id, "registration_id": row.pk, "name": row.name,
                 "status": row.status, "attended_at": row.latest_attended_at if row.status == "attended" else None}
        if manages and rbac.can(actor, rbac.Action.VIEW_AUDIT, row.event.makerspace_id):
            value.update(email=row.email, phone=row.phone)
            answers = row.custom_answers
            if isinstance(answers, dict) and answers.get("version") == 2:
                projector = answer_projector()
                if projector is None:
                    value.update(custom_answers=None, custom_answers_unavailable_reason="v2_projection_unavailable")
                    logger.warning("series_guest_v2_projection_unavailable", extra={
                        "event_id": row.event_id, "registration_id": row.pk})
                else:
                    value["custom_answers"] = projector(event=row.event, actor=actor, registration=row, snapshot=answers)
            else:
                value["custom_answers"] = answers
        grouped[key]["occurrences"].append(value)
    return [value for value in grouped.values() if value["occurrences"]]


class SeriesGuestsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event series"], request=None,
                   parameters=[OpenApiParameter("event_id", int), OpenApiParameter("status", str),
                               OpenApiParameter("attendance", str), OpenApiParameter("page", int)],
                   responses={200: SeriesGuestsPageSerializer, **ERRORS})
    def get(self, request, pk):
        if set(request.query_params) - set(GuestFilter().fields):
            raise ValidationError("Unknown query parameter.")
        filters = GuestFilter(data=request.query_params)
        filters.is_valid(raise_exception=True)
        series = event_authority.get_event(request.user, pk, VIEW, series=True)
        rows = authorized_registrations(series, request.user, filters.validated_data)
        identities = rows.annotate(registration_id=Case(
            When(member_id__isnull=True, then=F("pk")), default=Value(None), output_field=IntegerField(),
        )).values("member_id", "registration_id").order_by("member_id", "registration_id").distinct()
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(identities, request, view=self)
        data = project_guests(rows, page, actor=request.user)
        response = paginator.get_paginated_response(SeriesGuestSerializer(data, many=True).data)
        response["Cache-Control"] = "private, no-store"
        return response
