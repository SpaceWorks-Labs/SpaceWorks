from django.utils.translation import gettext
import json
from rest_framework import serializers

from apps.admin_api import bulk_import
from apps.admin_api.models import BulkImportJob


class BulkImportPreviewSerializer(serializers.Serializer):
    file = serializers.FileField(required=False)
    rows = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=False,
        max_length=bulk_import.MAX_IMPORT_ROWS,
    )
    mapping = serializers.JSONField(required=False)

    def validate(self, attrs):
        return _validate_import_payload(attrs)


class BulkImportJobCreateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=BulkImportJob.Mode.choices)
    file = serializers.FileField(required=False)
    rows = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=False,
        max_length=bulk_import.MAX_IMPORT_ROWS,
    )
    mapping = serializers.JSONField(required=False)

    def validate(self, attrs):
        return _validate_import_payload(attrs)


class BulkImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkImportJob
        fields = [
            "id",
            "mode",
            "status",
            "total_rows",
            "processed_rows",
            "created_count",
            "updated_count",
            "error_count",
            "warning_count",
            "result",
            "error",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields


class BulkImportSheetSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="The .xlsx workbook to read; only its first sheet is used.")


class BulkImportSheetResultSerializer(serializers.Serializer):
    rows = serializers.ListField(
        child=serializers.DictField(),
        help_text="One object per non-blank row, keyed by the first row's headers; blank cells are \"\".",
    )


def _validate_import_payload(attrs):
    attrs["mapping"] = _mapping_value(attrs.get("mapping"))
    has_file = bool(attrs.get("file"))
    has_rows = bool(attrs.get("rows"))
    if not has_file and not has_rows:
        raise serializers.ValidationError(gettext("Provide either file or rows."))
    if has_file and has_rows:
        raise serializers.ValidationError(gettext("Provide file or rows, not both."))
    uploaded_file = attrs.get("file")
    if uploaded_file and uploaded_file.size > bulk_import.MAX_IMPORT_UPLOAD_BYTES:
        raise serializers.ValidationError(
            {
                "file": (
                    gettext('Import file must be {MAX_IMPORT_UPLOAD_BYTES} bytes or smaller.').format(MAX_IMPORT_UPLOAD_BYTES=bulk_import.MAX_IMPORT_UPLOAD_BYTES)
                )
            }
        )
    return attrs



def _mapping_value(value):
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError({"mapping": gettext("Mapping must be valid JSON.")}) from exc
    if not isinstance(value, dict):
        raise serializers.ValidationError({"mapping": gettext("Mapping must be an object.")})
    return value



# Response shapes of the synchronous preview/apply routes (#193 OpenAPI contract).
class BulkImportRowMessagesSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    errors = serializers.DictField(child=serializers.CharField(), required=False, help_text="Field -> message.")
    warnings = serializers.DictField(child=serializers.CharField(), required=False, help_text="Field -> message.")


class BulkImportPlannedRowSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    action = serializers.ChoiceField(choices=("create", "update", "error"))
    data = serializers.JSONField(help_text="The normalised product fields for this row.")
    warnings = serializers.DictField(child=serializers.CharField())


class BulkImportSummarySerializer(serializers.Serializer):
    create = serializers.IntegerField()
    update = serializers.IntegerField()
    errors = serializers.IntegerField()
    warnings = serializers.IntegerField()
    total = serializers.IntegerField()


class BulkImportPreviewResultSerializer(serializers.Serializer):
    mapping = serializers.DictField(child=serializers.CharField())
    valid = serializers.BooleanField()
    errors = BulkImportRowMessagesSerializer(many=True)
    warnings = BulkImportRowMessagesSerializer(many=True)
    rows = BulkImportPlannedRowSerializer(many=True)
    summary = BulkImportSummarySerializer()


class BulkImportApplyResultSerializer(BulkImportPreviewResultSerializer):
    applied = serializers.BooleanField()
    partial = serializers.BooleanField(required=False)
    created = serializers.IntegerField(required=False)
    updated = serializers.IntegerField(required=False)
