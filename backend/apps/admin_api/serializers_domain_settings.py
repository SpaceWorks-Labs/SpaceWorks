"""Shapes for the per-domain settings endpoint.

These serializers describe and shape-check the request; the authoritative validation
(capability prerequisites, module checks, reminder bounds, request-access conflicts)
stays in `MakerspaceSerializer`, which `domain_settings.apply_domain_settings` reuses.
"""

from collections.abc import Mapping

from rest_framework import serializers

from apps.makerspaces.domain_settings import DOMAINS
from apps.makerspaces.models import Makerspace


_UNKNOWN = "Unknown or read-only setting."


class DomainFeatureSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    parent_module = serializers.CharField(allow_null=True)
    requires_features = serializers.ListField(child=serializers.CharField())
    enabled = serializers.BooleanField(help_text="Stored switch value.")
    available = serializers.BooleanField(
        help_text="Every module this switch needs is installed and shipped here."
    )


class DomainSettingValuesSerializer(serializers.Serializer):
    """Union of every domain's settings; a response carries only its own domain's."""

    event_default_registration_audience = serializers.ChoiceField(
        choices=Makerspace._meta.get_field("event_default_registration_audience").choices,
        required=False, help_text="events domain.",
    )
    event_reminder_lead_hours = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="events domain.",
    )
    booking_requester_notifications_enabled = serializers.BooleanField(
        required=False, help_text="bookings domain.",
    )
    booking_reminder_lead_hours = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="bookings domain.",
    )
    filament_low_stock_threshold_grams = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, help_text="machines domain.",
    )
    anonymous_requests_enabled = serializers.BooleanField(
        required=False, help_text="inventory domain.",
    )


class DomainSettingsSerializer(serializers.Serializer):
    domain = serializers.ChoiceField(choices=sorted(DOMAINS))
    editable = serializers.BooleanField(
        help_text=(
            "False for a type-scoped Machine Manager while machines outside their "
            "assigned types exist: machine settings are tenant-wide."
        )
    )
    features = DomainFeatureSerializer(many=True)
    settings = DomainSettingValuesSerializer()


class DomainSettingsUpdateSerializer(serializers.Serializer):
    features = serializers.DictField(
        child=serializers.BooleanField(), required=False,
        help_text="Feature key -> on/off. Only this domain's keys; others are refused.",
    )
    settings = DomainSettingValuesSerializer(required=False)

    def to_internal_value(self, data):
        # DRF drops unknown keys silently; a misspelled or foreign setting (including
        # `enabled_modules`) must be refused instead, never read as "nothing changed".
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected an object."]})
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError({key: _UNKNOWN for key in unknown})
        values = data.get("settings")
        if isinstance(values, Mapping):
            known = set(DomainSettingValuesSerializer().fields)
            unknown = sorted(set(values) - known)
            if unknown:
                raise serializers.ValidationError(
                    {"settings": {key: _UNKNOWN for key in unknown}}
                )
        return super().to_internal_value(data)
