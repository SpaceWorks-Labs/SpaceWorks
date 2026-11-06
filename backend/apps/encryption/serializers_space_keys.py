"""Shapes for the console's space keys API (#190 follow-up)."""

from rest_framework import serializers, status
from rest_framework.exceptions import APIException

from .key_events import KeyEventSerializer

KEY_ACTIONS = ("rotate_dek", "emergency_rekey", "rotate_search_key", "rotate_publishable_key")


class SlugMismatch(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "confirm_slug_mismatch"
    default_detail = {"code": "confirm_slug_mismatch", "confirm_slug": ["Type the space's web address name exactly."]}


def require_typed_slug(space, typed):
    if (typed or "").strip() != space.slug:
        raise SlugMismatch()


class SpaceKeyActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=KEY_ACTIONS)
    confirm_slug = serializers.CharField(max_length=100, help_text="The space's slug, typed back.")


class SpaceArchiveKeyActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("reencrypt", "purge"))
    confirm_slug = serializers.CharField(max_length=100, help_text="The space's slug, typed back.")


class ArchiveJobSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("reencrypt", "purge"))
    state = serializers.ChoiceField(choices=("queued", "running", "done", "failed"))
    error_code = serializers.CharField(allow_blank=True)
    updated_at = serializers.CharField()


class StaleArchiveSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    completed_at = serializers.DateTimeField(allow_null=True)
    size_bytes = serializers.IntegerField(allow_null=True)
    reencryptable = serializers.BooleanField()
    job = ArchiveJobSerializer(allow_null=True)


class SpaceArchiveJobQueuedSerializer(serializers.Serializer):
    archive_id = serializers.UUIDField()
    job = ArchiveJobSerializer(allow_null=True)


class _Version(serializers.Serializer):
    version = serializers.IntegerField()
    status = serializers.CharField()


class SpaceKeyStateSerializer(serializers.Serializer):
    active_dek_version = serializers.IntegerField(allow_null=True)
    dek_versions = _Version(many=True)
    search_key_version = serializers.IntegerField(allow_null=True)
    publishable_key_rotated_at = serializers.DateTimeField(allow_null=True)
    previous_publishable_key_valid_until = serializers.DateTimeField(allow_null=True)
    jobs = KeyEventSerializer(many=True)
    running = KeyEventSerializer(allow_null=True)
    pii_encryption_enabled = serializers.BooleanField()
    rls_mode = serializers.CharField()
    stale_archives = StaleArchiveSerializer(many=True)
