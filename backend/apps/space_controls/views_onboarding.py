"""Onboarding review in the web console (#185 item 5, #190). Managed deployments only
(``hosting_requests.availability.admin_available``): 404 on a self-host. Every
transition goes through ``hosting_requests.workflow``; approval also provisions."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.hosting_requests import workflow
from apps.hosting_requests.availability import admin_available
from apps.hosting_requests.models import HostingRequest
from apps.openapi_errors import errors

from . import onboarding

TAGS = ["Platform onboarding"]


class HostingRequestRowSerializer(serializers.ModelSerializer):
    inviter_summary = serializers.SerializerMethodField()
    created_makerspace = serializers.SerializerMethodField()

    class Meta:
        model = HostingRequest
        fields = ("id", "status", "source", "space_name", "proposed_slug", "location", "expected_members",
                  "applicant_name", "applicant_email", "applicant_phone", "space_website_url", "description",
                  "organization_choice", "new_organization_name", "inviter_summary", "created_at", "verified_at",
                  "decided_at", "changes_note", "created_makerspace")
        read_only_fields = fields

    def get_inviter_summary(self, obj) -> str:
        if obj.inviter_kind == HostingRequest.InviterKind.MAKERSPACE:
            return f"Invited via makerspace {obj.inviter_makerspace or '(deleted)'}"
        if obj.inviter_kind == HostingRequest.InviterKind.ORGANIZATION:
            return f"Invited via organization {obj.inviter_organization or '(deleted)'}"
        return "Public form"

    def get_created_makerspace(self, obj) -> dict | None:
        space = obj.created_makerspace
        return {"id": space.pk, "name": space.name, "slug": space.slug} if space else None


class OnboardingRevisionSerializer(serializers.Serializer):
    kind = serializers.CharField()
    note = serializers.CharField(allow_blank=True)
    changed_fields = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class HostingRequestDetailSerializer(HostingRequestRowSerializer):
    revisions = OnboardingRevisionSerializer(many=True, read_only=True)

    class Meta(HostingRequestRowSerializer.Meta):
        fields = (*HostingRequestRowSerializer.Meta.fields, "revisions")
        read_only_fields = fields


class OnboardingApproveSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    slug = serializers.SlugField(max_length=50, required=False, allow_blank=True, default="")
    organization_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    new_organization_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    invite_manager = serializers.BooleanField(default=True)


class OnboardingSpaceRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class OnboardingApproveResultSerializer(serializers.Serializer):
    request = HostingRequestRowSerializer()
    makerspace = OnboardingSpaceRefSerializer()
    invitation = serializers.CharField(
        help_text="The Space Manager invitation mail: an email delivery status, `skipped` or `unavailable`.")


class OnboardingChangesNoteSerializer(serializers.Serializer):
    note = serializers.CharField(min_length=10, max_length=2000)


class OnboardingRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=2000)


def _managed():
    if not admin_available():
        raise Http404()


class HostingRequestListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = HostingRequestRowSerializer

    @extend_schema(tags=TAGS, summary="List hosting (onboarding) requests",
                   parameters=[OpenApiParameter("status", str, enum=[value for value, _ in HostingRequest.Status.choices])],
                   responses={200: HostingRequestRowSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request):
        _managed()
        rows = HostingRequest.objects.select_related("created_makerspace", "inviter_makerspace", "inviter_organization")
        wanted = request.query_params.get("status")
        if wanted:
            rows = rows.filter(status=wanted)
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(HostingRequestRowSerializer(page, many=True).data)


class HostingRequestDetailView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Read one hosting request with its review history",
                   responses={200: HostingRequestDetailSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        _managed()
        row = get_object_or_404(HostingRequest.objects.prefetch_related("revisions"), pk=pk)
        return Response(HostingRequestDetailSerializer(row).data)


class HostingRequestApproveView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Approve a request: create the space and invite its Space Manager",
                   request=OnboardingApproveSerializer, responses={200: OnboardingApproveResultSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        _managed()
        get_object_or_404(HostingRequest, pk=pk)
        body = OnboardingApproveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row, space, invitation = onboarding.approve(request.user, pk, **body.validated_data)
        return Response(OnboardingApproveResultSerializer({"request": row, "makerspace": space, "invitation": invitation}).data)


class HostingRequestChangesView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Ask the applicant for changes", request=OnboardingChangesNoteSerializer,
                   responses={200: HostingRequestRowSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        _managed()
        body = OnboardingChangesNoteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(HostingRequestRowSerializer(workflow.request_changes(request.user, pk, body.validated_data["note"])).data)


class HostingRequestRejectView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Reject a hosting request with a reason", request=OnboardingRejectSerializer,
                   responses={200: HostingRequestRowSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        _managed()
        body = OnboardingRejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(HostingRequestRowSerializer(workflow.reject(request.user, pk, body.validated_data["reason"])).data)
