"""Closed metadata commands; neither object keys nor hashes authorize bytes."""
from rest_framework import serializers
from .serializers import StageCommand


class StageFileCreateCommand(StageCommand):
    expected_response_version = serializers.IntegerField(min_value=1)
    question_id = serializers.RegexField(r"^[A-Za-z0-9_-]{1,64}$")
    filename = serializers.CharField(max_length=255)
    size_bytes = serializers.IntegerField(min_value=1, max_value=10485760)
    mime = serializers.ChoiceField(choices=("application/pdf", "image/jpeg", "image/png", "image/heic"))


class StageFileCompleteCommand(StageCommand):
    generation = serializers.IntegerField(min_value=1)


class StageFileSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    version = serializers.IntegerField()
    generation = serializers.IntegerField()
    state = serializers.CharField()
    question_id = serializers.CharField()
    purpose = serializers.CharField()
    expected_bytes = serializers.IntegerField()
    actual_bytes = serializers.IntegerField(allow_null=True)
    canonical_mime = serializers.CharField()
    sha256 = serializers.CharField()
    scan_status = serializers.CharField()
    error_code = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)


class StageUploadDescriptorSerializer(serializers.Serializer):
    method = serializers.CharField()
    url = serializers.URLField()
    fields = serializers.DictField(child=serializers.CharField())
    expires_at = serializers.DateTimeField()
    generation = serializers.IntegerField()


class StageFileCreatedSerializer(StageFileSerializer):
    upload = StageUploadDescriptorSerializer(allow_null=True)


class StageFileCommandResult(serializers.Serializer):
    id = serializers.IntegerField()
    asset_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
