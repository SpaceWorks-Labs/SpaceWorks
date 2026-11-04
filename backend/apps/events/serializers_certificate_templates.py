from rest_framework import serializers

from apps.events.certificate_artwork_storage import MAX_BYTES
from apps.events.certificate_templates import normalize_certificate_template
from apps.operations.printable_serializers import PrintInputSerializer, PositionedElementSerializer
from .certificates.serializers_layout import CertificateLayerSerializer


class CertificateParametersSerializer(PrintInputSerializer):
    version = serializers.IntegerField(min_value=1, max_value=2, required=False)
    page_width_mm = serializers.FloatField(min_value=100, max_value=420, required=False)
    page_height_mm = serializers.FloatField(min_value=100, max_value=420, required=False)
    grid_mm = serializers.FloatField(min_value=0.5, max_value=10, required=False)
    name_box = PositionedElementSerializer(required=False)
    layers = CertificateLayerSerializer(many=True, required=False, max_length=20)


class CertificateTemplateWriteSerializer(PrintInputSerializer):
    parameters = CertificateParametersSerializer()
    artwork_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)

    def validate_parameters(self, value):
        return normalize_certificate_template(value)


class CertificateTemplateCommandSerializer(CertificateTemplateWriteSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class CertificateTemplateRevisionSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    parameters = CertificateParametersSerializer()
    artwork_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    event_version = serializers.IntegerField(required=False)


class CertificateTemplateCommandResultSerializer(CertificateTemplateRevisionSerializer):
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class CertificateArtworkPresignSerializer(PrintInputSerializer):
    content_type = serializers.ChoiceField(choices=("image/png", "image/jpeg"))
    content_length = serializers.IntegerField(min_value=1, max_value=MAX_BYTES)


class CertificateArtworkUploadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    upload_url = serializers.URLField()
    headers = serializers.DictField(child=serializers.CharField())


class CertificateArtworkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    resource_id = serializers.UUIDField()
