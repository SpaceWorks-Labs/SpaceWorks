"""Closed request/response schemas for every Lane B route."""
from rest_framework import serializers
from .asset_preview import KINDS as ASSET_PREVIEW_KINDS
from .serializers_requirements import ProjectRequirementsSerializer


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({"detail": "Expected an object."})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unknown field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class CommandSerializer(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class DeclarationSerializer(ClosedSerializer):
    used = serializers.BooleanField()
    details = serializers.CharField(max_length=5000, allow_blank=True)


class LinkSerializer(ClosedSerializer):
    kind = serializers.ChoiceField(choices=["repo", "demo", "video", "slides", "cad", "pcb", "firmware", "other"])
    url = serializers.URLField(max_length=2048)
    public_requested = serializers.BooleanField(default=False)


class ProjectPatchSerializer(CommandSerializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    tagline = serializers.CharField(max_length=300, required=False, allow_blank=True)
    problem = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    description = serializers.CharField(max_length=30000, required=False, allow_blank=True)
    challenges = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    tech_tags = serializers.ListField(child=serializers.CharField(max_length=50), max_length=30, required=False)
    ai_declaration = DeclarationSerializer(required=False)
    reuse_declaration = DeclarationSerializer(required=False)
    form_answers = serializers.DictField(required=False)
    track_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=30, required=False)
    prize_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=30, required=False)
    asset_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, required=False)
    public_asset_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, required=False)
    public_requested = serializers.BooleanField(required=False)
    links = LinkSerializer(many=True, max_length=30, required=False)


class AmendSerializer(CommandSerializer):
    reason = serializers.CharField(max_length=1000)
    patch = serializers.DictField()


class TriageSerializer(CommandSerializer):
    triage = serializers.ChoiceField(choices=["pending", "eligible", "ineligible", "hidden"])
    reason = serializers.CharField(max_length=1000)


class UploadSerializer(ClosedSerializer):
    filename = serializers.CharField(max_length=240)
    mime = serializers.CharField(max_length=160)
    bytes = serializers.IntegerField(min_value=1, max_value=2 * 1024 ** 3)
    group = serializers.ChoiceField(choices=["fab-2d", "fab-3dprint", "fab-cnc", "hardware-cad",
        "hardware-pcb", "firmware", "source", "embroidery", "archives", "video", "deck", "images", "model"])
    subtype = serializers.CharField(max_length=32, required=False, default="auto")


class ResumeUploadSerializer(ClosedSerializer):
    filename = serializers.CharField(max_length=240)
    bytes = serializers.IntegerField(min_value=1, max_value=10 * 1024 ** 2)
    mime = serializers.ChoiceField(choices=["application/pdf", "application/octet-stream"])


class FromSavedSerializer(ClosedSerializer):
    saved_asset_id = serializers.IntegerField(min_value=1)
    saved_detail_version = serializers.IntegerField(min_value=1)


class AssetCommandSerializer(CommandSerializer):
    generation = serializers.IntegerField(min_value=1)


class PartsSerializer(AssetCommandSerializer):
    part_numbers = serializers.ListField(child=serializers.IntegerField(min_value=1, max_value=10000), max_length=100)


class AssetResponseSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    generation = serializers.IntegerField()
    state = serializers.CharField()
    bytes = serializers.IntegerField()
    mime = serializers.CharField(allow_blank=True)
    sha256 = serializers.CharField(allow_blank=True)
    expires_at = serializers.DateTimeField(allow_null=True)
    allowed_actions = serializers.ListField(child=serializers.CharField())
    filename = serializers.CharField(required=False)
    extension = serializers.CharField(required=False)
    kind = serializers.CharField(required=False)
    media_metadata = serializers.DictField(required=False)
    preview = serializers.ChoiceField(choices=ASSET_PREVIEW_KINDS, required=False,
        help_text="The in-browser preview this file offers; `download` means download-only.")
    preview_max_bytes = serializers.IntegerField(allow_null=True, required=False,
        help_text="A preview bound below the upload cap; a larger file is download-only.")


class ProjectResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    snapshot_id = serializers.IntegerField(allow_null=True)
    project = serializers.DictField(required=False)
    requirements = ProjectRequirementsSerializer(required=False)
    allowed_actions = serializers.ListField(child=serializers.CharField())


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()


class UploadDescriptorSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["POST", "MULTIPART"])
    url = serializers.URLField(required=False)
    fields = serializers.DictField(child=serializers.CharField(), required=False)
    expires_at = serializers.DateTimeField(required=False)
    part_size = serializers.IntegerField(required=False)
    part_count = serializers.IntegerField(required=False)


class UploadResponseSerializer(AssetResponseSerializer):
    upload = UploadDescriptorSerializer(required=False)


class AssetCommandResponseSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    event_id = serializers.IntegerField(required=False)
    state = serializers.CharField()
    version = serializers.IntegerField(required=False)
    status_url = serializers.CharField(required=False)
    sponsor_consents_revoked = serializers.BooleanField(required=False)


class PartResponseSerializer(serializers.Serializer):
    part_number = serializers.IntegerField()
    size_bytes = serializers.IntegerField()
    url = serializers.URLField()


class PartsResponseSerializer(serializers.Serializer):
    parts = PartResponseSerializer(many=True)


class ResumePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AssetResponseSerializer(many=True)
