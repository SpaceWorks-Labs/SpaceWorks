"""Public-stat settings input/output and typed validation errors."""
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import APIException

from apps.hardware_requests.exceptions import ErrorSerializer
from . import public_stats_settings as group
from .public_stats_catalogue import WIDGETS


class PublicStatsSettingsInputError(APIException):
    status_code = 400

    def __init__(self, errors):
        super().__init__({"detail": gettext("Invalid public statistics settings."),
                          "code": "invalid_public_stats_settings", "errors": errors})


@extend_schema_serializer(component_name="PublicStatsSettingsError")
class PublicStatsSettingsErrorSerializer(ErrorSerializer):
    errors = serializers.JSONField(required=False)


class _KeyListField(serializers.ListField):
    def __init__(self, allowed, limit, **kwargs):
        super().__init__(child=serializers.ChoiceField(choices=list(allowed)), max_length=limit, **kwargs)

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        if len(set(values)) != len(values):
            raise serializers.ValidationError(gettext("Each key may appear once."))
        return values


class PublicStatsSettingsSerializer(serializers.Serializer):
    visibility = serializers.DictField(child=serializers.BooleanField(), required=False,
        help_text="Partial visibility overrides, keyed by choices.widgets. Missing keys keep their stored values.")

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError({"unknown_fields": unknown})
        return super().to_internal_value(data)

    def validate_visibility(self, value):
        unknown = sorted(set(value) - set(WIDGETS))
        if unknown:
            raise serializers.ValidationError(gettext("Unknown public statistics: {keys}.").format(keys=", ".join(unknown)))
        return value

    def validate(self, attrs):
        if not attrs or (set(attrs) == {"visibility"} and not attrs["visibility"]):
            raise serializers.ValidationError(gettext("Provide at least one public statistics setting."))
        return attrs

    enabled = serializers.BooleanField(help_text="The public stats page is published.")
    sections = _KeyListField(group.SECTIONS, len(group.SECTIONS),
                             help_text="Shown sections in page order; a section left out is off.")
    # A CharField, not a ChoiceField: a second `period` enum would rename the existing PeriodEnum.
    period = serializers.CharField(help_text="month, year, all or fy: the one period every period count uses; "
                                             "visitors cannot change it.")
    headline = _KeyListField(group.METRICS, group.MAX_HEADLINE,
                             help_text="Up to four metric keys shown first; a hidden section's metric is skipped.")
    tv_mode_enabled = serializers.BooleanField(help_text="Serve the full-screen TV page at /stats/tv.")
    tv_refresh_seconds = serializers.IntegerField(min_value=group.TV_REFRESH_MIN, max_value=group.TV_REFRESH_MAX)

    def validate_period(self, value):
        if value not in group.PERIODS:
            raise serializers.ValidationError(gettext('Choose one of: {value}.').format(value=', '.join(group.PERIODS)))
        return value


class _ChoiceSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()


class _MetricChoiceSerializer(_ChoiceSerializer):
    section = serializers.CharField()


class _WidgetChoiceSerializer(_MetricChoiceSerializer):
    owner_module = serializers.CharField()
    kind = serializers.ChoiceField(choices=["count", "hours", "weight", "list", "detail"])


class _DecisionSerializer(serializers.Serializer):
    editable = serializers.BooleanField()
    locked = serializers.BooleanField()
    can_lock = serializers.BooleanField(help_text="The caller may use the L17 lock API for this exact key.")
    available = serializers.BooleanField(help_text="The source module/public surface is currently available; never enables it.")
    code = serializers.CharField(allow_null=True)
    via = serializers.CharField(allow_null=True)


class _CapabilitiesSerializer(serializers.Serializer):
    settings = serializers.DictField(child=_DecisionSerializer())
    visibility = serializers.DictField(child=_DecisionSerializer())


class _ChoicesSerializer(serializers.Serializer):
    sections = _ChoiceSerializer(many=True)
    periods = _ChoiceSerializer(many=True)
    metrics = _MetricChoiceSerializer(many=True)
    widgets = _WidgetChoiceSerializer(many=True)
    max_headline = serializers.IntegerField()
    tv_refresh_min = serializers.IntegerField()
    tv_refresh_max = serializers.IntegerField()


class PublicStatsSettingsResponseSerializer(serializers.Serializer):
    settings = PublicStatsSettingsSerializer()
    can_edit = serializers.BooleanField(help_text="Legacy page-wide edit flag; use capabilities for individual settings.")
    choices = _ChoicesSerializer()
    capabilities = _CapabilitiesSerializer()
