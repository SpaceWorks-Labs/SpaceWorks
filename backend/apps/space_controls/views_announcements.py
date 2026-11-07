"""Announcements (superadmin), the signed-in notices feed and the public paused check."""

from django.utils.translation import gettext
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import public_availability_queryset
from apps.openapi_errors import errors

from . import announcements, notices
from .models import PlatformAnnouncement

TAGS = ["Platform announcements"]


class PlatformAnnouncementSerializer(serializers.ModelSerializer):
    makerspaces = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = PlatformAnnouncement
        fields = ("id", "title", "body", "severity", "audience", "makerspaces", "starts_at", "ends_at", "send_email",
                  "show_to_members", "email_sent_at", "email_recipient_count", "cancelled_at", "created_by",
                  "created_at", "status")
        read_only_fields = fields

    def get_makerspaces(self, obj) -> list[dict]:
        return [{"id": row.makerspace_id, "name": row.makerspace.name} for row in obj.targets.select_related("makerspace")]

    def get_created_by(self, obj) -> str | None:
        return (obj.created_by.display_name or obj.created_by.username) if obj.created_by else None

    def get_status(self, obj) -> str:
        return announcements.status(obj)


class PlatformAnnouncementCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=4000)
    severity = serializers.ChoiceField(choices=PlatformAnnouncement.Severity.choices, default="info")
    audience = serializers.ChoiceField(choices=PlatformAnnouncement.Audience.choices, default="all_spaces")
    makerspace_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)
    starts_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    ends_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    send_email = serializers.BooleanField(default=False)
    show_to_members = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs.get("ends_at") and attrs.get("starts_at") and attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({"ends_at": gettext("End after the start.")})
        return attrs


class AnnouncementListCreateView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = PlatformAnnouncementSerializer

    @extend_schema(tags=TAGS, summary="List platform announcements",
                   responses={200: PlatformAnnouncementSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        page = self.paginate_queryset(PlatformAnnouncement.objects.select_related("created_by"))
        return self.get_paginated_response(PlatformAnnouncementSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Create a banner announcement (and optional email to Space Managers)",
                   request=PlatformAnnouncementCreateSerializer, responses={201: PlatformAnnouncementSerializer, **errors(400, 401, 403)})
    def post(self, request):
        body = PlatformAnnouncementCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = announcements.create(request.user, body.validated_data)
        return Response(PlatformAnnouncementSerializer(row).data, status=status.HTTP_201_CREATED)


class AnnouncementDetailView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Read a platform announcement",
                   responses={200: PlatformAnnouncementSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        return Response(PlatformAnnouncementSerializer(get_object_or_404(PlatformAnnouncement, pk=pk)).data)


class AnnouncementCancelView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Cancel a platform announcement", request=None,
                   responses={200: PlatformAnnouncementSerializer, **errors(401, 403, 404, 409)})
    def post(self, request, pk):
        get_object_or_404(PlatformAnnouncement, pk=pk)
        return Response(PlatformAnnouncementSerializer(announcements.cancel(request.user, pk)).data)


class PlatformNoticeAnnouncementSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()
    severity = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True)
    makerspace_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The viewer's spaces this announcement reaches (empty for the superadmin = every space).")
    member_makerspace_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The viewer's spaces where it reaches them as a member; member pages show only these.")


class PlatformNoticeSpaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    state = serializers.ChoiceField(choices=("read_only", "suspended"))
    reason = serializers.CharField(allow_blank=True)
    since = serializers.DateTimeField(allow_null=True)


class PlatformNoticesSerializer(serializers.Serializer):
    announcements = PlatformNoticeAnnouncementSerializer(many=True)
    spaces = PlatformNoticeSpaceSerializer(many=True)


class PlatformNoticesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Live announcements and paused or read-only spaces for this account",
                   responses={200: PlatformNoticesSerializer, **errors(401)})
    def get(self, request):
        return Response(PlatformNoticesSerializer(notices.notices_for(request.user)).data)


class SpacePausedStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=("active", "paused"))


class PublicAvailabilityView(APIView):
    """Tells the SPA to show "This space is paused" instead of a not-found page.

    Reveals only that a space exists and is paused (its public pages are offline anyway);
    an archived or unknown space stays a 404, exactly like every other public route."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=TAGS, summary="Whether a public space is paused", responses={200: SpacePausedStateSerializer,
                                                                                    **errors(404)})
    def get(self, request, makerspace_slug):
        spaces = Makerspace.objects.filter(slug=str(makerspace_slug or "").strip())
        space = public_availability_queryset(spaces).first()
        if space is None:
            raise Http404()
        paused = space.lifecycle_state == Makerspace.LifecycleState.SUSPENDED
        return Response(SpacePausedStateSerializer({"state": "paused" if paused else "active"}).data)
