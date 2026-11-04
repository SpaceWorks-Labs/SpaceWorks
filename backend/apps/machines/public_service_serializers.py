from rest_framework import serializers

from apps.machines.public_printer_service_serializers import PublicPrinterStatusSerializer


class PublicMachineServiceSubmitSerializer(serializers.Serializer):
    certification_override_reason = serializers.CharField(required=False, allow_blank=True, max_length=1000, write_only=True)
    website = serializers.CharField(required=False, allow_blank=True)
    machine_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)
    source_link = serializers.URLField(required=False, allow_blank=True, max_length=200)
    capability_payload = serializers.JSONField(required=False)


class PublicMachineServiceSubmitResponseSerializer(serializers.Serializer):
    public_token = serializers.UUIDField()
    status = serializers.CharField()


class PublicMachineServiceStatusSerializer(PublicPrinterStatusSerializer):
    """The generic token endpoint's complete allowlist. Never add contact, owner,
    machine or other-job identifiers; ``status`` uses the canonical ``in_progress``."""

    machine_type_name = serializers.CharField()
