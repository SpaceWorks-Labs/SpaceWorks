"""Event insights for a space or an organisation's hosted events (parity E-B7, `events.space_insights`).

Both routes answer with the same closed, counts-only payload and the same k >= 10 suppression. They
never accept an event or person id, so the only scope is the one the caller's authority already grants.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.events.models import Event
from apps.events.views_invites import ERRORS
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_q

from .analytics_org import hosted_insights

FEATURE = "events.space_insights"


class TopEventSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    attended = serializers.IntegerField(min_value=0)


class ReturningShareSerializer(serializers.Serializer):
    suppressed = serializers.BooleanField(help_text="True when fewer than k distinct attendees exist.")
    attendees = serializers.IntegerField(allow_null=True)
    returning_percent = serializers.FloatField(allow_null=True)


class EventInsightsSerializer(serializers.Serializer):
    window_days = serializers.IntegerField()
    k = serializers.IntegerField()
    top_events = TopEventSerializer(many=True)
    returning = ReturningShareSerializer()


def _respond(events):
    response = Response(EventInsightsSerializer(hosted_insights(events)).data)
    response["Cache-Control"] = "private, no-store"
    return response


class SpaceEventInsightsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: EventInsightsSerializer, **ERRORS},
        parameters=[OpenApiParameter("makerspace", int, required=True, description="The space to summarise.")],
        description="Top events over the last 180 days by attendance and the share of returning attendees for "
                    "one space. Needs the space's manage_events action and events.space_insights (404 while "
                    "off). Groups under 10 are suppressed; no person is ever returned.")
    def get(self, request):
        try:
            space_id = int(request.query_params.get("makerspace", ""))
        except ValueError:
            raise Http404 from None
        space = get_object_or_404(Makerspace, pk=space_id)
        # Cross-tenant callers get 404, not 403: the space's existence is not theirs to learn.
        if not rbac.can(request.user, rbac.Action.MANAGE_EVENTS, space.pk):
            raise Http404
        require_module(space, "events")
        require_feature(space, FEATURE)
        return _respond(Event.objects.filter(makerspace=space))


class OrganizationEventInsightsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: EventInsightsSerializer, **ERRORS},
        description="The same insight over the events an organisation hosts, across every space where "
                    "events.space_insights is on. Needs an organisation governance role. Groups under 10 "
                    "are suppressed; no person is ever returned.")
    def get(self, request, pk):
        from apps.organizations import governance
        from apps.organizations.views_admin import _organization
        organization = _organization(request.user, pk)
        if not governance.actions_for(request.user, organization):
            raise PermissionDenied()
        spaces = [space.pk for space in Makerspace.objects.filter(
            pk__in=Event.objects.filter(organizers__organization=organization).values("makerspace_id"))
            if feature_enabled(space, FEATURE)]
        hosted = Event.objects.filter(servable_q("makerspace"), makerspace_id__in=spaces,
                                      makerspace__enabled_modules__contains=["events"],
                                      pk__in=Event.objects.filter(organizers__organization=organization).values("pk"))
        return _respond(hosted)
