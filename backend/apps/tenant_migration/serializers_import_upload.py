"""Boundary schemas for the resumable ciphertext upload protocol."""

from rest_framework import serializers

from .import_staging import MAX_ARCHIVE_BYTES
from .serializers import TypedErrorSerializer


class ImportUploadStartSerializer(serializers.Serializer):
    source_archive_digest = serializers.RegexField(r"^[0-9a-f]{64}$")
    archive_bytes = serializers.IntegerField(min_value=1, max_value=MAX_ARCHIVE_BYTES)


class ImportUploadConflictSerializer(TypedErrorSerializer):
    upload_received_bytes = serializers.IntegerField(
        required=False, help_text="Authoritative next offset when code is offset_mismatch.",
    )
