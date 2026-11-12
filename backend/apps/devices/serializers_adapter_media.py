"""Response serializers for the media/data staff and member routes (decision 321). Read-only; no object key, no digest."""
from rest_framework import serializers

from apps.devices.serializers_identity import StrictSerializer
from apps.devices.models import AdapterArtifact, AdapterConfigVersion, AdapterEvent


class ArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdapterArtifact
        fields = ("id", "binding", "kind", "content_type", "size_bytes", "status", "service_request_id", "session_id",
                  "captured_at", "created_at", "expires_at")
        read_only_fields = fields


class DetectionSerializer(serializers.ModelSerializer):
    kind = serializers.CharField(source="data.kind", read_only=True)
    confidence = serializers.FloatField(source="data.confidence", read_only=True)
    artifact_id = serializers.CharField(source="data.artifact_id", read_only=True, default=None)
    note = serializers.CharField(source="data.note", read_only=True, default="")

    class Meta:
        model = AdapterEvent
        fields = ("id", "binding", "kind", "confidence", "artifact_id", "note", "observed_at", "received_at")
        read_only_fields = fields


class OwnerDetectionSerializer(DetectionSerializer):
    """What the job owner sees: the kind, confidence and time; never the free-text note."""

    class Meta(DetectionSerializer.Meta):
        fields = ("id", "kind", "confidence", "artifact_id", "observed_at")
        read_only_fields = fields


class ConfigVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdapterConfigVersion
        fields = ("id", "version", "config", "created_at", "ack_outcome", "ack_detail", "acked_at")
        read_only_fields = fields


class ConfigPushSerializer(StrictSerializer):
    config = serializers.DictField()


class TalkSerializer(StrictSerializer):
    active = serializers.BooleanField()
