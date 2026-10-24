"""Closed owner upload commands; finance read purpose comes from the row."""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from .serializers import Command, Integer


class PayeeFileCreateCommand(Command):
    payee_revision_id = serializers.UUIDField()
    expected_payee_version = Integer(min_value=1)
    question_id = serializers.ChoiceField(choices=("routing_document",))
    filename = serializers.CharField(max_length=255)
    bytes = Integer(min_value=1, max_value=10485760)
    mime = serializers.ChoiceField(choices=("application/pdf", "image/jpeg", "image/png"))


class FinanceFileCommand(Command):
    expected_asset_version = Integer(min_value=1)
    generation = Integer(min_value=1)


class FinanceAttachmentReadQuery(serializers.Serializer):
    """No purpose, token or arbitrary object key is accepted in the query."""


class FileStatus(serializers.Serializer):
    asset_id = Integer()
    generation = Integer()
    version = Integer()
    state = serializers.CharField()
    filename = serializers.CharField()
    bytes = Integer()
    sha256 = serializers.CharField()
    scan_status = serializers.CharField()
    error_code = serializers.CharField()


@extend_schema_serializer(component_name="PayoutUploadDescriptor")
class UploadDescriptor(serializers.Serializer):
    method = serializers.CharField()
    url = serializers.URLField()
    fields = serializers.DictField()
    expires_at = serializers.DateTimeField()


class FileCreated(serializers.Serializer):
    asset_id = Integer()
    generation = Integer()
    state = serializers.CharField()
    upload = UploadDescriptor(required=False)


class FileCompleted(serializers.Serializer):
    id = serializers.UUIDField()
    version = Integer()
    asset_id = Integer()
    generation = Integer()
    state = serializers.CharField()
    status_url = serializers.CharField()
