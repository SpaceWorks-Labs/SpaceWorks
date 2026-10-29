"""Staff settings routes for the public event surface (L1).

* `GET/PUT admin/makerspaces/<id>/events/embed-policy/` -- the event embed allow-list;
* `GET/PATCH admin/makerspaces/<id>/events/report-switches/` -- DY-61;
* `GET admin/events/host-options/` -- DY-63, the spaces the actor may host an event in.

Reads need event authority in the space (the Event Manager, Space Manager or superadmin);
writes go through the settings-authority layer and answer a typed 403 otherwise.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from . import report_switches

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 423)}


def private(data):
    return Response(data, headers={"Cache-Control": "private, no-store"})


def _space(request, makerspace_id):
    from .views_admin_event_detail import _visible_makerspace
    return _visible_makerspace(request.user, makerspace_id)


class EmbedPolicySerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    allowed_origins = serializers.ListField(child=serializers.CharField(max_length=255), max_length=20)

    def validate_allowed_origins(self, value):
        from apps.makerspaces.website_origins import validate_origins
        return validate_origins(value)


class EventEmbedPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Read the event embed allow-list", request=None,
                   description="404 while `events.embed` is off.",
                   responses={200: EmbedPolicySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.makerspaces.folded_capabilities import require_capability
        from .embed_policy import FEATURE, policy_for
        space = require_capability(_space(request, makerspace_id), FEATURE)
        return private(EmbedPolicySerializer(policy_for(space)).data)

    @extend_schema(tags=["Admin events"], summary="Replace the event embed allow-list",
                   description="Off by default. Origins are exact lowercase https:// origins (frame-ancestors). "
                               "Settings authority: the Space Manager, or the Event Manager with the events "
                               "settings grant. Audited as `event.embed_policy_updated`.",
                   request=EmbedPolicySerializer,
                   responses={200: EmbedPolicySerializer, 400: OpenApiResponse(ErrorSerializer), **ERRORS})
    def put(self, request, makerspace_id):
        from .embed_policy import save_policy
        space = _space(request, makerspace_id)
        data = EmbedPolicySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return private(EmbedPolicySerializer(save_policy(space, actor=request.user, **data.validated_data)).data)


class ReportSwitchSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=report_switches.KEYS)
    label = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    enabled = serializers.BooleanField(help_text="Stored switch.")
    effective = serializers.BooleanField(help_text="On, with events and reports installed.")
    editable = serializers.BooleanField()
    locked = serializers.BooleanField()
    code = serializers.CharField(allow_null=True, help_text="Why it is read-only, when it is.")


class ReportSwitchesSerializer(serializers.Serializer):
    switches = ReportSwitchSerializer(many=True)


class ReportSwitchesInput(serializers.Serializer):
    switches = serializers.DictField(child=serializers.BooleanField(), allow_empty=False)

    def validate_switches(self, value):
        unknown = sorted(set(value) - set(report_switches.KEYS))
        if unknown:
            raise serializers.ValidationError({key: "Not an event report switch." for key in unknown})
        return value


class EventReportSwitchesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Read the event report switches (DY-61)", request=None,
                   responses={200: ReportSwitchesSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        return private(ReportSwitchesSerializer(report_switches.describe(request.user, space)).data)

    @extend_schema(tags=["Admin events"], summary="Switch the event PDF and event exports (DY-61)",
                   description="The Space Manager always; the Event Manager only with the events settings "
                               "grant and never past a lock (`setting_not_delegated` / `setting_locked`). "
                               "Each change is audited as `settings.changed`.",
                   request=ReportSwitchesInput, responses={200: ReportSwitchesSerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        data = ReportSwitchesInput(data=request.data)
        data.is_valid(raise_exception=True)
        saved = report_switches.apply(request.user, space, data.validated_data["switches"])
        return private(ReportSwitchesSerializer(report_switches.describe(request.user, saved)).data)


class HostOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class EventHostOptionsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Spaces the caller may host a new event in (DY-63)",
                   description="Spaces with events on where the caller holds event authority; a request "
                               "from a space's own staff origin lists only that space.",
                   request=None, responses={200: HostOptionSerializer(many=True), **ERRORS})
    def get(self, request):
        from .directories import host_makerspaces
        rows = host_makerspaces(request.user, request)[:200]
        return private(HostOptionSerializer(rows, many=True).data)
