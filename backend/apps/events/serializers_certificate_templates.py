from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema_field
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


@extend_schema_field({"type": "object", "description": (
    "The closed version 1/2 layout (see CertificateParameters), or a Card Studio certificate: a version 3 card design "
    "document with kind `certificate` (CARD-STUDIO-SPEC-0.12.0.md section 12).")})
class CertificateParametersField(serializers.Field):
    """The closed v1/v2 layout, or a Studio v3 certificate document (validated by `normalize_certificate_template`)."""

    def to_internal_value(self, data):
        if isinstance(data, dict) and data.get("version") == 3:
            return data
        serializer = CertificateParametersSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def to_representation(self, value):
        if isinstance(value, dict) and value.get("version") == 3:
            return value
        return CertificateParametersSerializer(value).data


KIND_CHOICES = ("", "attendance", "participant", "finalist", "winner", "volunteer_thanks",
                "mentor_thanks", "judge_thanks", "organiser_thanks")


class CertificateTemplateWriteSerializer(PrintInputSerializer):
    parameters = CertificateParametersField()
    artwork_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    certificate_kind = serializers.ChoiceField(choices=KIND_CHOICES, required=False, default="", help_text=(
        "Blank saves the event default design; a kind saves that kind's own design."))

    def validate_parameters(self, value):
        return normalize_certificate_template(value)


class CertificatePreviewSerializer(CertificateTemplateWriteSerializer):
    sample_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="",
                                        help_text="Sample recipient name for this preview only; never stored.")


class CertificateTemplateCommandSerializer(CertificateTemplateWriteSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class CertificateTemplateRevisionSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    parameters = CertificateParametersField()
    artwork_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    event_version = serializers.IntegerField(required=False)
    certificate_kind = serializers.CharField(required=False, allow_blank=True)
    uses_default = serializers.BooleanField(required=False, help_text="True when this kind has no design of its own.")
    own_designs = serializers.ListField(child=serializers.CharField(), required=False,
                                        help_text="Certificate kinds that have a design of their own.")


class CertificateTemplateCommandResultSerializer(CertificateTemplateRevisionSerializer):
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


SIGNATURE_MAX_BYTES = 2 * 1024 * 1024


class CertificateArtworkPresignSerializer(PrintInputSerializer):
    content_type = serializers.ChoiceField(choices=("image/png", "image/jpeg", "image/webp"))
    content_length = serializers.IntegerField(min_value=1, max_value=MAX_BYTES)
    purpose = serializers.ChoiceField(choices=("artwork", "signature"), required=False, default="artwork",
                                      help_text="A signature is PNG, JPEG or WebP up to 2 MB; artwork is PNG or JPEG up to 10 MiB.")

    def validate(self, data):
        if data["purpose"] == "signature" and data["content_length"] > SIGNATURE_MAX_BYTES:
            raise serializers.ValidationError({"content_length": gettext("A signature image must be at most 2 MB.")})
        if data["purpose"] == "artwork" and data["content_type"] == "image/webp":
            raise serializers.ValidationError({"content_type": gettext("Artwork must be PNG or JPEG.")})
        return data


class CertificateArtworkUploadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    upload_url = serializers.URLField()
    headers = serializers.DictField(child=serializers.CharField())


class CertificateArtworkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    resource_id = serializers.UUIDField()
