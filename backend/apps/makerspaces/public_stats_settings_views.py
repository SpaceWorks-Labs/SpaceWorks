"""Staff API for Settings › Public stats (#170). Writes go through `public_stats_settings`."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from . import public_stats_settings as group
from .models import Makerspace
from .servability import servable_queryset


class _KeyListField(serializers.ListField):
    def __init__(self, allowed, limit, **kwargs):
        super().__init__(child=serializers.ChoiceField(choices=list(allowed)), max_length=limit, **kwargs)

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        if len(set(values)) != len(values):
            raise serializers.ValidationError("Each key may appear once.")
        return values


class PublicStatsSettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(help_text="The public stats page is published.")
    sections = _KeyListField(group.SECTIONS, len(group.SECTIONS),
                             help_text="Shown sections in page order; a section left out is off.")
    period = serializers.ChoiceField(choices=list(group.PERIODS),
                                     help_text="The one period every period count uses; visitors cannot change it.")
    headline = _KeyListField(group.METRICS, group.MAX_HEADLINE,
                             help_text="Up to four metric keys shown first; a hidden section's metric is skipped.")
    tv_mode_enabled = serializers.BooleanField(help_text="Serve the full-screen TV page at /stats/tv.")
    tv_refresh_seconds = serializers.IntegerField(min_value=group.TV_REFRESH_MIN, max_value=group.TV_REFRESH_MAX)


class _ChoiceSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()


class _MetricChoiceSerializer(_ChoiceSerializer):
    section = serializers.CharField()


class _ChoicesSerializer(serializers.Serializer):
    sections = _ChoiceSerializer(many=True)
    periods = _ChoiceSerializer(many=True)
    metrics = _MetricChoiceSerializer(many=True)
    max_headline = serializers.IntegerField()
    tv_refresh_min = serializers.IntegerField()
    tv_refresh_max = serializers.IntegerField()


class PublicStatsSettingsResponseSerializer(serializers.Serializer):
    settings = PublicStatsSettingsSerializer()
    can_edit = serializers.BooleanField(help_text="False: read-only for this actor (Space Manager only).")
    choices = _ChoicesSerializer()


def _payload(actor, space, config):
    from .settings_authority import decide
    allowed = decide(actor, space, group.MODULE, group.setting_key("sections")).allowed
    return {"settings": config, "can_edit": allowed, "choices": group.choices()}


_ERRORS = {code: ErrorSerializer for code in (401, 403, 404)}
_HEADERS = {"Cache-Control": "private, no-store"}


class PublicStatsSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    def space(self, request, makerspace_id):
        rows = rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MAKERSPACE,
                                                  servable_queryset(Makerspace.objects.all()), field="pk")
        return get_object_or_404(rows, pk=makerspace_id)

    @extend_schema(tags=["Admin makerspaces"], summary="Read the public stats settings", request=None,
                   description="Staff of the space read the group; only the Space Manager (or the superadmin) "
                               "may change it, which `can_edit` reports.",
                   responses={200: PublicStatsSettingsResponseSerializer, **_ERRORS})
    def get(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        return Response(_payload(request.user, space, group.read_config(space)), headers=_HEADERS)

    @extend_schema(tags=["Admin makerspaces"], summary="Save the public stats settings",
                   description="Each changed key is written through the settings authority (module `public_site`, "
                               "Space Manager only) and audited as `settings.changed`. 403 `setting_not_delegated` "
                               "for anyone else.",
                   request=PublicStatsSettingsSerializer,
                   responses={200: PublicStatsSettingsResponseSerializer,
                              **{code: ErrorSerializer for code in (400, 401, 403, 404, 423)}})
    def put(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        data = PublicStatsSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        saved = group.save_config(request.user, space, dict(data.validated_data))
        return Response(_payload(request.user, space, saved), headers=_HEADERS)
