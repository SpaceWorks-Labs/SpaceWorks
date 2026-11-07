"""Organiser routes for event ID cards and ticket designs (SPEC §4.4, §9, X49).

Every organiser of the event -- anyone holding its edit permission (Q-I9) -- manages
designs and cards, with no approval unless an event, its organisation or the space
turned approval on (#136). Door staff (check-in permission) may scan cards.
"""
from django.utils.translation import gettext
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.openapi_errors import errors
from apps.card_designs.serializers import CardJobCreateSerializer, CardJobSerializer
from apps.card_designs.serializers_openapi import CardDesignPairSerializer, ReasonSerializer

from .id_cards_openapi import (
    CardRoleRequestSerializer, CardScanRequestSerializer, CardScanResultSerializer, IssueResultSerializer,
)

from . import id_cards
from .event_permissions import CHECK_IN, EDIT_DETAILS
from .models import Event, EventIdCard

TAGS = ["Event ID cards"]


def organiser_event(actor, pk, permission=EDIT_DETAILS):
    from apps.card_designs.switches import event_cards_on
    from . import event_authority
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk)
    if not event_cards_on(event.makerspace):
        raise NotFound()
    event_authority.require(actor, event, permission)
    return event


def organiser_card(actor, pk):
    card = get_object_or_404(EventIdCard.objects.select_related("event__makerspace", "registration"), pk=pk)
    organiser_event(actor, card.event_id)
    return card


class EventIdCardSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    """Printed names and revoke reasons are scoped PII: masked for a superadmin without a window."""

    photo_set = serializers.SerializerMethodField()

    class Meta:
        model = EventIdCard
        fields = ("id", "event", "registration", "role", "printed_name", "status", "valid_until", "issued_at",
                  "revoked_at", "last_emailed_at", "photo_set")
        read_only_fields = fields

    def get_photo_set(self, obj) -> bool:
        return bool(obj.photo_object_key)


class EventCardDesignsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="This event's card and ticket designs (created from Event pass on first use)",
                   request=None, parameters=[OpenApiParameter("ticket_type", int)],
                   responses={200: CardDesignPairSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        from apps.card_designs.resolution import get_or_create
        from apps.card_designs.serializers import CardDesignSerializer
        from apps.card_designs.switches import domain_on
        event = organiser_event(request.user, pk)
        ticket_type = None
        if request.query_params.get("ticket_type"):
            from .models import EventTicketType
            ticket_type = get_object_or_404(EventTicketType, pk=request.query_params["ticket_type"], event=event)
        result = {}
        for domain in ("event_card", "event_ticket"):
            if not domain_on(event.makerspace, domain):
                continue
            design, _created = get_or_create(event.makerspace, domain, actor=request.user, event=event,
                                             ticket_type=ticket_type)
            result[domain] = CardDesignSerializer(design, context={"request": request}).data
        return Response(result)


class EventIdCardListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="This event's ID cards", request=None,
                   responses={200: EventIdCardSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, pk):
        event = organiser_event(request.user, pk)
        rows = EventIdCard.objects.filter(event=event).order_by("-issued_at")[:1000]
        return Response(EventIdCardSerializer(rows, many=True, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Issue cards now to every confirmed registrant", request=None,
                   responses={200: IssueResultSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        event = organiser_event(request.user, pk)
        if not id_cards.has_published_design(event):
            raise ValidationError({"detail": gettext("Publish the event card design first.")})
        issued, revoked = id_cards.reconcile_event(event.pk, actor=request.user)
        return Response({"issued": issued, "revoked": revoked})


class EventIdCardRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Revoke an event card with a reason", request=ReasonSerializer,
                   responses={200: EventIdCardSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        card = id_cards.revoke(request.user, organiser_card(request.user, pk), str(request.data.get("reason", "")))
        return Response(EventIdCardSerializer(card, context={"request": request}).data)


class EventIdCardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Change a card's role (attendee, speaker, mentor, judge, volunteer, crew)",
                   request=CardRoleRequestSerializer, responses={200: EventIdCardSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        card = id_cards.set_role(request.user, organiser_card(request.user, pk), request.data.get("role"))
        return Response(EventIdCardSerializer(card, context={"request": request}).data)


class EventIdCardDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download one event card", request=None,
                   parameters=[OpenApiParameter("format", str), OpenApiParameter("side", str)],
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        from apps.card_designs.cards import render
        from apps.card_designs.downloads import record_download
        card = organiser_card(request.user, pk)
        fmt, side = request.query_params.get("format", "pdf"), request.query_params.get("side", "front")
        data, content_type, filename = render("event_card", card, fmt=fmt, side=side)
        record_download(request.user, "event_card", card, fmt, side)
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class EventCardJobView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="My card jobs for this event", request=None,
                   responses={200: CardJobSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, pk):
        from apps.card_designs.jobs import my_jobs
        return Response(my_jobs(request.user, "event", organiser_event(request.user, pk).pk))

    @extend_schema(tags=TAGS, summary="Queue a bulk job for this event's active cards", request=CardJobCreateSerializer,
                   responses={201: CardJobSerializer, 200: CardJobSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.card_designs.jobs import enqueue
        from apps.card_designs.serializers import CardJobCreateSerializer, CardJobSerializer
        from apps.card_designs.views_jobs import job_params
        event = organiser_event(request.user, pk)
        data = CardJobCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        from .id_cards_preview import event_card_ids
        params = {"explicit": False} if values["kind"] == "email" else job_params(values)
        job, created = enqueue(request.user, event.makerspace, values["kind"], scope="event", scope_id=event.pk,
                               targets=event_card_ids(event, values), params=params,
                               revision=list(event.card_designs.values_list("published_revision", flat=True)))
        return Response(CardJobSerializer(job).data, status=201 if created else 200)


class EventCardScanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Scan a card at the door: find (and optionally check in) the registration",
                   request=CardScanRequestSerializer, responses={200: CardScanResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.audit import services as audit
        from .services_checkin_cards import candidates, check_in
        from . import event_authority
        event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk)
        # Door scanning needs only the events module and check-in authority: a member card
        # identifies its holder whether or not this space issues event ID cards.
        event_authority.require(request.user, event, CHECK_IN)
        rows = candidates(event, str(request.data.get("payload", ""))[:300], request.user)
        confirmable = [row for row in rows if row.status == "registered"]
        checked = None
        if request.data.get("check_in") is True and len(confirmable) == 1:
            updated = check_in(event, confirmable[0], request.user)[0]
            checked = updated.pk
            rows = [updated if row.pk == checked else row for row in rows]
            audit.record(request.user, "card.scanned_for_checkin", makerspace=event.makerspace, target=confirmable[0],
                         meta={"place": "event_door", "event_id": event.pk, "registration_id": checked})
        response = Response({"checked_in": checked, "registrations": [
            {"registration_id": row.pk, "name": row.name, "status": row.status,
             "confirmable": row.status == "registered"} for row in rows]})
        response["Cache-Control"] = "private, no-store"
        return response
