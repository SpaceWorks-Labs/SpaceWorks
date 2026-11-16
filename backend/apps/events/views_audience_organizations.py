from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from .event_permissions import EDIT_DETAILS
from .serializers_public import EventOrganizerSummarySerializer
from .services_audience_organizations import MAX_AUDIENCE_ORGANIZATIONS, replace_audience_organizations
from .views_admin_event_detail import _manageable_event


class EventAudienceOrganizationReplaceSerializer(serializers.Serializer):
    organization_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        max_length=MAX_AUDIENCE_ORGANIZATIONS, allow_empty=True,
    )


class EventAudienceOrganizationListSerializer(serializers.Serializer):
    audience_organizations = EventOrganizerSummarySerializer(many=True, read_only=True)


class EventAudienceOrganizationView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin events"],
        summary="Replace an event's selected audience organizations",
        description=("Members of these organizations may register when the event's audience is "
                     "'participating_organizations'. Grants no event management authority. "
                     "Newly added organizations must be findable in the organization directory."),
        request=EventAudienceOrganizationReplaceSerializer,
        responses={
            200: EventAudienceOrganizationListSerializer,
            400: OpenApiResponse(description="Invalid or unavailable organization."),
            **{code: ErrorSerializer for code in (401, 403, 404)},
            409: OpenApiResponse(ErrorSerializer, description="The event is cancelled or completed."),
        },
    )
    def put(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        serializer = EventAudienceOrganizationReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = replace_audience_organizations(
            event, actor=request.user,
            organization_ids=serializer.validated_data["organization_ids"],
        )
        return Response(EventAudienceOrganizationListSerializer({"audience_organizations": rows}).data)
