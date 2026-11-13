"""Members discover help categories through their live event participation."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from apps.events.contributions.api_common import ProgrammeView, paginated, page_schema
from apps.events.contributions.serializers import ERRORS
from apps.events.submissions.boundary_runtime import ProgrammeBoundary
from .models_queue import EventHelpType


class MemberHelpTopicSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()


class MemberHelpTopicListView(ProgrammeView):
    @extend_schema(tags=["Event mentoring"], responses={200: page_schema("MemberHelpTopicPage", MemberHelpTopicSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        event = self.event(request, pk, makerspace_id)
        ProgrammeBoundary().participant(event, request.user)
        return paginated(request, EventHelpType.objects.filter(event=event).order_by("priority", "pk"),
            lambda row: {"key": row.key, "label": row.label})
