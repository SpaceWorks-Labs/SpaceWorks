"""Superadmin space controls in the web console (#185, #190): health cards and the
lifecycle controls. Superadmin-only, recent re-authentication on every write, audited by
the services. /control/ offers the same services as its fallback."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

from . import health, serializers as s, services_access, services_ownership, services_schedule
from .errors import SpaceControlConflict

TAGS = ["Platform space controls"]


class SpaceHealthListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = s.HealthCardSerializer

    @extend_schema(tags=TAGS, summary="List every space's health card (archived and paused included)",
                   parameters=[OpenApiParameter("state", str, enum=s.STATES), OpenApiParameter("search", str)],
                   responses={200: s.HealthCardSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        rows = Makerspace.objects.order_by("name", "pk")
        text = (request.query_params.get("search") or "").strip()
        if text:
            rows = rows.filter(Q(name__icontains=text) | Q(slug__icontains=text) | Q(public_code__iexact=text))
        wanted = request.query_params.get("state")
        if wanted in s.STATES:
            # State is derived, so filter after building cards (bounded by the page anyway).
            cards = [card for card in (health.card(space, viewer=request.user) for space in rows[:500]) if card["state"] == wanted]
            page = self.paginate_queryset(cards)
            return self.get_paginated_response(s.HealthCardSerializer(page, many=True).data)
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(s.HealthCardSerializer([health.card(space, viewer=request.user) for space in page], many=True).data)


class SpaceHealthDetailView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Read one space's health card with its open problems",
                   responses={200: s.HealthCardDetailSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        return Response(s.HealthCardDetailSerializer(health.card(space, detail=True, viewer=request.user)).data)


class _ControlView(RecentReauthenticationMixin, APIView):
    """One POST that runs a control service and answers the space's fresh health card.

    Subclasses declare ``request_serializer`` and implement ``run``; each documents its
    own ``post`` so the OpenAPI summary is per route.
    """

    permission_classes = [IsActiveSuperAdmin]
    request_serializer = s.SpaceControlEmptySerializer

    def control(self, request, makerspace_id):
        get_object_or_404(Makerspace, pk=makerspace_id)
        body = self.request_serializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            self.run(request.user, makerspace_id, body.validated_data)
        except DjangoValidationError as exc:
            raise PermissionDenied(" ".join(exc.messages)) from exc
        return Response(s.HealthCardSerializer(health.card(Makerspace.objects.get(pk=makerspace_id), viewer=request.user)).data)


CONTROL_ERRORS = errors(400, 401, 403, 404, 409)


class SuspendView(_ControlView):
    request_serializer = s.SpaceControlReasonSerializer

    def run(self, actor, pk, data):
        services_access.suspend(actor, pk, data["reason"])

    @extend_schema(tags=TAGS, summary="Pause (suspend) a space", request=s.SpaceControlReasonSerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class UnsuspendView(_ControlView):
    def run(self, actor, pk, data):
        services_access.unsuspend(actor, pk)

    @extend_schema(tags=TAGS, summary="Unblock a paused space", request=s.SpaceControlEmptySerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class ReadOnlyView(_ControlView):
    request_serializer = s.SpaceControlReasonSerializer

    def run(self, actor, pk, data):
        services_access.set_read_only(actor, pk, data["reason"])

    @extend_schema(tags=TAGS, summary="Put a space in read-only mode", request=s.SpaceControlReasonSerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class ReadOnlyLiftView(_ControlView):
    def run(self, actor, pk, data):
        services_access.lift_read_only(actor, pk)

    @extend_schema(tags=TAGS, summary="End read-only mode for a space", request=s.SpaceControlEmptySerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class ScheduleView(_ControlView):
    request_serializer = s.SpaceScheduleRequestSerializer

    def run(self, actor, pk, data):
        # Every schedule ends in a purge, so it takes the same typed-slug confirmation.
        data = dict(data)
        if data.pop("confirm_slug") != Makerspace.objects.get(pk=pk).slug:
            raise ValidationError({"confirm_slug": "Type the space's slug exactly to confirm.", "code": "slug_mismatch"})
        services_schedule.schedule(actor, pk, **data)

    @extend_schema(tags=TAGS, summary="Schedule a space's archive and its purge after a grace period",
                   request=s.SpaceScheduleRequestSerializer, responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class ScheduleCancelView(_ControlView):
    def run(self, actor, pk, data):
        services_schedule.cancel(actor, pk)

    @extend_schema(tags=TAGS, summary="Cancel a scheduled archive or purge", request=s.SpaceControlEmptySerializer,
                   responses={200: s.HealthCardSerializer, **CONTROL_ERRORS})
    def post(self, request, makerspace_id):
        return self.control(request, makerspace_id)


class TransferOwnershipView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Assign a new Space Manager (transfer ownership)",
                   request=s.SpaceTransferRequestSerializer,
                   responses={200: s.SpaceTransferResultSerializer, **errors(400, 401, 403, 404, 409, 423)})
    def post(self, request, makerspace_id):
        get_object_or_404(Makerspace, pk=makerspace_id)
        body = s.SpaceTransferRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            outcome, delivery = services_ownership.transfer_ownership(request.user, makerspace_id, **body.validated_data)
        except DjangoValidationError as exc:
            raise PermissionDenied(" ".join(exc.messages)) from exc
        card = health.card(Makerspace.objects.get(pk=makerspace_id), viewer=request.user)
        return Response(s.SpaceTransferResultSerializer(
            {"status": outcome, "card": card, "invitation_email_status": delivery}).data, status=status.HTTP_200_OK)


__all__ = [
    "SpaceHealthListView", "SpaceHealthDetailView", "SuspendView", "UnsuspendView", "ReadOnlyView",
    "ReadOnlyLiftView", "ScheduleView", "ScheduleCancelView", "TransferOwnershipView", "SpaceControlConflict",
]
