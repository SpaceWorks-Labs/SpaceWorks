"""Public attribution and private account-specific eligibility are separate contracts."""

from django.db.models.manager import BaseManager
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class ParticipatingOrganizationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class OrganizationAudienceListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        from .organization_audience import audience_projections
        rows = list(data.all() if isinstance(data, BaseManager) else data)
        flags = self.context.setdefault("event_feature_flags", {})
        self.context["organization_audience_projection"] = audience_projections(rows, feature_flags=flags)
        return super().to_representation(rows)


class OrganizationAudienceFields(serializers.Serializer):
    participating_organizations = serializers.SerializerMethodField()
    audience_label = serializers.SerializerMethodField()

    class Meta:
        list_serializer_class = OrganizationAudienceListSerializer

    def _projection(self, obj):
        from .organization_audience import audience_projection
        # Per-serialization only; no account information or shared eligibility cache.
        key = (obj._meta.label, obj.pk)
        cache = self.context.setdefault("organization_audience_projection", {})
        if key not in cache:
            cache[key] = audience_projection(obj)
        return cache[key]

    @extend_schema_field(ParticipatingOrganizationSerializer(many=True))
    def get_participating_organizations(self, obj):
        return self._projection(obj)["participating_organizations"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_audience_label(self, obj):
        from .organization_audience import AUDIENCE
        return self._projection(obj)["audience_label"] if obj.registration_audience == AUDIENCE else None


class HostWaiverProjectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    version = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)


class EventEligibilitySerializer(serializers.Serializer):
    eligible = serializers.BooleanField(read_only=True)
    reason = serializers.CharField(read_only=True, allow_null=True)
    consent_repair_required = serializers.BooleanField(read_only=True)
    host_waiver = HostWaiverProjectionSerializer(read_only=True, allow_null=True)
