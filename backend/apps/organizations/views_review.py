"""Organization review queue, decisions, resubmission and the governor roll-up (O-B5)."""
from drf_spectacular.utils import extend_schema_serializer
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveStaff
from apps.organizations import governance, services_review
from apps.organizations.access import is_superadmin, require_governance
from apps.organizations.models import Organization, OrganizationReview
from apps.organizations.serializers_admin import OrganizationSummarySerializer
from apps.organizations.services_console import require_superadmin
from apps.organizations.views_admin import _organization
from apps.organizations.views_console import console_errors
from django.utils.translation import gettext


class ReviewEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationReview
        fields = ("id", "action", "reason", "created_at")
        read_only_fields = fields


class ReviewQueueRowSerializer(serializers.ModelSerializer):
    submitted_by = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ("id", "slug", "name", "description", "website", "review_status", "created_at", "submitted_by")
        read_only_fields = fields

    def get_submitted_by(self, obj) -> str:
        return obj.created_by.username if obj.created_by else ""


class ReviewQueueSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = ReviewQueueRowSerializer(many=True)


@extend_schema_serializer(component_name="OrganizationReviewDecision")
class ReviewDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=sorted(services_review.DECISIONS))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ReviewResubmitSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class RollupSerializer(serializers.Serializer):
    people = serializers.DictField(child=serializers.IntegerField())
    spaces = serializers.ListField(child=serializers.DictField())
    home_space_card_note = serializers.CharField()


class OrganizationReviewQueueView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin organizations"], summary="Organization review queue (superadmin)",
        parameters=[OpenApiParameter("status", str, description="Review status; default pending_review.")],
        responses={200: ReviewQueueSerializer, **console_errors(400, 401, 403)})
    def get(self, request):
        require_superadmin(request.user)
        status = request.query_params.get("status", Organization.ReviewStatus.PENDING_REVIEW)
        if status not in Organization.ReviewStatus.values:
            raise serializers.ValidationError({"status": gettext("Unknown review status.")})
        paginator = PageNumberPagination()
        rows = paginator.paginate_queryset(
            Organization.objects.filter(review_status=status).select_related("created_by")
            .order_by("created_at", "id"), request, view=self)
        return paginator.get_paginated_response(ReviewQueueRowSerializer(rows, many=True).data)


class OrganizationReviewView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin organizations"], summary="Organization review history", request=None,
                   responses={200: ReviewEntrySerializer(many=True), **console_errors(401, 403, 404)})
    def get(self, request, pk):
        organization = _organization(request.user, pk)
        if not is_superadmin(request.user):
            require_governance(request.user, organization, governance.MANAGE_ORGANIZATION_PROFILE)
        return Response(ReviewEntrySerializer(organization.reviews.all()[:100], many=True).data)

    @extend_schema(tags=["Admin organizations"], summary="Decide an organization review (superadmin)",
                   request=ReviewDecisionSerializer,
                   responses={200: OrganizationSummarySerializer, **console_errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        require_superadmin(request.user)
        organization = get_object_or_404(Organization, pk=pk)
        require_recent_reauth(request)
        payload = ReviewDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = services_review.decide(organization, request.user, **payload.validated_data)
        row.actor_memberships = []
        return Response(OrganizationSummarySerializer(row, context={"actor": request.user}).data)


class OrganizationResubmitView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin organizations"], summary="Resubmit an organization after requested changes",
                   request=ReviewResubmitSerializer,
                   responses={200: OrganizationSummarySerializer, **console_errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        organization = _organization(request.user, pk)
        payload = ReviewResubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = services_review.resubmit(organization, request.user, **payload.validated_data)
        row.actor_memberships = list(getattr(organization, "actor_memberships", []))
        return Response(OrganizationSummarySerializer(row, context={"actor": request.user}).data)


class OrganizationMemberRollupView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin organizations"], summary="Member roll-up (counts only, never names)",
                   request=None, responses={200: RollupSerializer, **console_errors(401, 403, 404)})
    def get(self, request, pk):
        from apps.organizations.org_member_rollup import member_rollup
        organization = _organization(request.user, pk)
        require_governance(request.user, organization, governance.MANAGE_ORGANIZATION_MEMBERS)
        response = Response(member_rollup(organization))
        response["Cache-Control"] = "no-store"
        return response
