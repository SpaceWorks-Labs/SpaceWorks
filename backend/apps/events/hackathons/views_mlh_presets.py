"""EP-9: the approved MLH application presets staff can switch MLH data sharing on with.

Same authority as the hackathon configuration it feeds (full manager; the event's programme gate decides),
read-only, and static per deployment: the presets live in `forms_schema.mlh_presets`.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response

from apps.events import event_authority
from apps.forms_schema.mlh_presets import mlh_presets

from .api_base import AdminView, ProgrammeCommandThrottle
from .api_schema import ERRORS


class MlhPresetSerializer(serializers.Serializer):
    id = serializers.CharField()
    label = serializers.CharField()
    schema = serializers.JSONField(help_text="A closed, age-free form-v2 schema to store as `optional_mlh_schema`.")


class MlhPresetsView(AdminView):
    permission = None
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme"], request=None, responses={200: MlhPresetSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, None)
        from .admission_errors import fail
        from .admission_feature import admission_enabled
        if not admission_enabled(event.makerspace):
            fail("not_found", "Not found.", status=404)
        return Response(mlh_presets())
