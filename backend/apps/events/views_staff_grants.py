from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff, active_user
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.origin_scope import (
    AMBIGUOUS_STAFF_ORIGIN_SCOPE, NO_STAFF_ORIGIN_SCOPE, staff_origin_scope,
)

from . import event_authority, services_staff_grants as services
from .models import Event, EventSeries, EventStaffGrant, EventStaffGrantInvite
from .serializers_admin import EmptyActionSerializer
from .serializers_staff_grants import (
    StaffGrantInviteCreatedSerializer, StaffGrantInviteInputSerializer,
    StaffGrantInviteListSerializer, StaffGrantInviteSerializer,
    StaffGrantListSerializer, StaffGrantPermissionsSerializer,
    StaffGrantRedeemSerializer, StaffGrantSerializer,
)
from .views_invites import PAGE_PARAMETERS, paginated

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}


class StaffGrantRedeemThrottle(SimpleRateThrottle):
    scope = "event_staff_grant_redeem"
    rate = "10/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class EventStaffGrantListView(APIView):
    permission_classes = [IsActiveStaff]
    series = False

    def target(self, request, pk):
        return event_authority.get_event(request.user, pk, None, series=self.series)

    def rows(self, model, target):
        return model.objects.filter(
            **{"series" if self.series else "event": target},
            makerspace_id=target.makerspace_id,
        ).order_by("id")

    @extend_schema(tags=["Admin events"], request=None, parameters=PAGE_PARAMETERS,
                   responses={200: StaffGrantListSerializer, **ERRORS})
    def get(self, request, pk):
        return paginated(request, self.rows(EventStaffGrant, self.target(request, pk)), StaffGrantSerializer)


class EventStaffInviteListView(EventStaffGrantListView):
    @extend_schema(tags=["Admin events"], request=None, parameters=PAGE_PARAMETERS,
                   responses={200: StaffGrantInviteListSerializer, **ERRORS})
    def get(self, request, pk):
        return paginated(request, self.rows(EventStaffGrantInvite, self.target(request, pk)), StaffGrantInviteSerializer)

    @extend_schema(tags=["Admin events"], request=StaffGrantInviteInputSerializer,
                   responses={201: StaffGrantInviteCreatedSerializer, **ERRORS})
    def post(self, request, pk):
        target = self.target(request, pk)
        serializer = StaffGrantInviteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, token = services.create_invite(target, actor=request.user, **serializer.validated_data)
        response = Response({**StaffGrantInviteSerializer(row).data, "token": token}, status=201)
        response["Cache-Control"] = "private, no-store"
        return response


def _manageable_row(actor, model, pk):
    rows = model.objects.select_related("event__makerspace", "series__makerspace").filter(
        event_id__in=event_authority.visible_events(actor, Event.objects.all()).values("pk"),
    ) | model.objects.select_related("event__makerspace", "series__makerspace").filter(
        series_id__in=event_authority.visible_events(actor, EventSeries.objects.all()).values("pk"),
    )
    row = get_object_or_404(rows, pk=pk)
    event_authority.require(actor, row.event if row.event_id else row.series, None)
    return row


class EventStaffGrantDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=StaffGrantPermissionsSerializer,
                   responses={200: StaffGrantSerializer, **ERRORS})
    def patch(self, request, pk):
        row = _manageable_row(request.user, EventStaffGrant, pk)
        serializer = StaffGrantPermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(StaffGrantSerializer(services.update_permissions(
            row, actor=request.user, **serializer.validated_data,
        )).data)


class EventStaffGrantRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=EmptyActionSerializer,
                   responses={200: StaffGrantSerializer, **ERRORS})
    def post(self, request, pk):
        row = _manageable_row(request.user, EventStaffGrant, pk)
        EmptyActionSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(StaffGrantSerializer(services.revoke_grant(row, actor=request.user)).data)


class EventStaffInviteRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=EmptyActionSerializer,
                   responses={200: StaffGrantInviteSerializer, **ERRORS})
    def post(self, request, pk):
        row = _manageable_row(request.user, EventStaffGrantInvite, pk)
        EmptyActionSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(StaffGrantInviteSerializer(services.revoke_invite(row, actor=request.user)).data)


class EventStaffInviteRedeemView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [StaffGrantRedeemThrottle]

    @extend_schema(tags=["Events"], request=StaffGrantRedeemSerializer,
                   responses={200: StaffGrantSerializer, **ERRORS})
    def post(self, request):
        if not active_user(request.user):
            raise PermissionDenied()
        scope = staff_origin_scope(request)
        if scope is AMBIGUOUS_STAFF_ORIGIN_SCOPE:
            raise PermissionDenied()
        serializer = StaffGrantRedeemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = services.redeem_invite(
            serializer.validated_data["token"], actor=request.user,
            makerspace_id=None if scope is NO_STAFF_ORIGIN_SCOPE else scope,
        )
        response = Response(StaffGrantSerializer(grant).data)
        response["Cache-Control"] = "private, no-store"
        return response
