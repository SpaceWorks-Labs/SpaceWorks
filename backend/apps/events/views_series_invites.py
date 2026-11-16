"""Series allowlist routes (parity E-B5, B12/B14). Entries hold an email digest only, so none is shown."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from . import event_authority, series_invites
from .event_permissions import MANAGE_INVITATIONS
from .feature_gates import require_feature
from .models import EventInvite, EventSeries
from .serializers_admin import EmptyActionSerializer
from .views_series import manageable_series

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}
TAGS = ["Admin event series"]


class SeriesInviteInput(serializers.Serializer):
    emails = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=series_invites.MAX_BATCH,
                                   write_only=True)
    expires_at = serializers.DateTimeField(allow_null=True, required=False)


class SeriesInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventInvite
        fields = ("id", "expires_at", "revoked_at", "created_at")
        read_only_fields = fields


class SeriesInviteListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SeriesInviteSerializer(many=True)


class SeriesInviteCreatedSerializer(serializers.Serializer):
    created = SeriesInviteSerializer(many=True)
    skipped = serializers.IntegerField(help_text="Emails that were already on the allowlist.")


class SeriesInviteListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List a series' allowlist entries", request=None,
                   parameters=[OpenApiParameter("page", int)], responses={200: SeriesInviteListSerializer, **ERRORS})
    def get(self, request, pk):
        series = manageable_series(request.user, pk, MANAGE_INVITATIONS)
        require_feature(series, series_invites.FEATURE)
        pager = PageNumberPagination()
        pager.page_size = 24
        page = pager.paginate_queryset(EventInvite.objects.filter(series=series).order_by("id"), request)
        return pager.get_paginated_response(SeriesInviteSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Allow emails to register for every occurrence of a series",
                   request=SeriesInviteInput, responses={201: SeriesInviteCreatedSerializer, **ERRORS})
    def post(self, request, pk):
        series = manageable_series(request.user, pk, MANAGE_INVITATIONS)
        payload = SeriesInviteInput(data=request.data)
        payload.is_valid(raise_exception=True)
        created, skipped = series_invites.add(series, actor=request.user, **payload.validated_data)
        return Response({"created": SeriesInviteSerializer(created, many=True).data, "skipped": skipped}, status=201)


class SeriesInviteRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Remove an allowlist entry", request=EmptyActionSerializer,
                   responses={200: SeriesInviteSerializer, **ERRORS})
    def post(self, request, pk):
        visible = event_authority.visible_events(request.user, EventSeries.objects.all()).values("pk")
        invite = get_object_or_404(EventInvite.objects.filter(series_id__in=visible), pk=pk)
        manageable_series(request.user, invite.series_id, MANAGE_INVITATIONS)
        payload = EmptyActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(SeriesInviteSerializer(series_invites.revoke(invite, actor=request.user)).data)
