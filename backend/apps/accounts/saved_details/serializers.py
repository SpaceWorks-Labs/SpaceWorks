"""Closed command inputs and explicit owner-only HTTP projections."""
from rest_framework import serializers


class SavedVaultClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"code": "invalid_input", "fields": {"body": ["Unexpected fields."]}})
        return super().to_internal_value(data)


class SavedVaultCommand(SavedVaultClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)

    def validate_expected_version(self, value):
        if type(self.initial_data.get("expected_version")) is not int:
            raise serializers.ValidationError("Use an integer version.")
        return value


class SavedVaultDetailPut(SavedVaultCommand):
    value = serializers.JSONField()
    save_consent = serializers.BooleanField()

    def validate_save_consent(self, value):
        if self.initial_data.get("save_consent") is not True:
            raise serializers.ValidationError("Explicit save consent is required.")
        return value


class SavedVaultDetailResponse(serializers.Serializer):
    field_key = serializers.CharField()
    value = serializers.JSONField(required=False)
    deleted = serializers.BooleanField(required=False)
    version = serializers.IntegerField()


class SavedVaultSavedField(serializers.Serializer):
    field_key = serializers.CharField()
    value = serializers.JSONField(allow_null=True, help_text="Null is a deletion tombstone; version remains available for safe recreation.")
    version = serializers.IntegerField()
    sensitive = serializers.BooleanField()
    default_save = serializers.BooleanField()


class SavedVaultDetailsResponse(serializers.Serializer):
    version = serializers.IntegerField()
    fields = SavedVaultSavedField(many=True)
    readiness = serializers.ChoiceField(choices=["ready", "unavailable"])


class SavedVaultPrefillSelector(SavedVaultClosedSerializer):
    event_id = serializers.IntegerField(min_value=1)
    makerspace_id = serializers.IntegerField(min_value=1)
    subject_kind = serializers.ChoiceField(choices=["registration", "application", "role_assignment"])
    subject_id = serializers.IntegerField(min_value=1, required=False)
    posting_id = serializers.IntegerField(min_value=1, required=False)


class SavedVaultPrefillInput(SavedVaultClosedSerializer):
    context = SavedVaultPrefillSelector()
    form_id = serializers.CharField(max_length=100)
    form_revision = serializers.IntegerField(min_value=1)
    event_date_revision = serializers.IntegerField(min_value=1)


class SavedVaultPrefillResponse(serializers.Serializer):
    form_revision = serializers.IntegerField()
    event_date_revision = serializers.IntegerField()
    values = serializers.DictField(child=serializers.JSONField())
    saved_detail_versions = serializers.DictField(child=serializers.IntegerField())
    save_defaults = serializers.DictField(child=serializers.BooleanField())
    derivation_inputs = serializers.DictField(child=serializers.JSONField())


class SavedVaultResumeInput(SavedVaultClosedSerializer):
    filename = serializers.CharField(max_length=255)
    bytes = serializers.IntegerField(min_value=1)  # domain cap returns the specified 413
    mime = serializers.ChoiceField(choices=["application/pdf"])


class SavedVaultCompleteInput(SavedVaultCommand):
    generation = serializers.IntegerField(min_value=1)


class SavedVaultUploadResponse(serializers.Serializer):
    method = serializers.ChoiceField(choices=["POST"])
    url = serializers.URLField()
    fields = serializers.DictField(child=serializers.CharField())
    expires_at = serializers.DateTimeField()


class SavedVaultResumeResponse(serializers.Serializer):
    asset_id = serializers.IntegerField()
    state = serializers.ChoiceField(choices=["uploading", "validating", "ready", "failed", "deleting", "deleted"])
    sha256 = serializers.CharField(required=False)
    bytes = serializers.IntegerField(required=False)
    version = serializers.IntegerField(required=False)
    generation = serializers.IntegerField(required=False)
    upload = SavedVaultUploadResponse(required=False)
    status_url = serializers.CharField(required=False)
    code = serializers.CharField(required=False)


class SavedVaultIntentField(serializers.Serializer):
    state = serializers.ChoiceField(choices=["applied", "conflict", "failed"])
    version = serializers.IntegerField(required=False)
    current_version = serializers.IntegerField(required=False)
    code = serializers.CharField(required=False)


class SavedVaultIntentResponse(serializers.Serializer):
    operation_id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=["pending", "applied", "conflict", "failed"])
    fields = serializers.DictField(child=SavedVaultIntentField())
    retryable = serializers.BooleanField()
    code = serializers.CharField(required=False)


class SavedVaultExportResponse(serializers.Serializer):
    job_id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=["queued", "building", "ready", "failed", "expired"])
    expires_at = serializers.DateTimeField(required=False)
    status_url = serializers.CharField(required=False)


class SavedVaultEmptyInput(SavedVaultClosedSerializer):
    pass


class SavedVaultErrorResponse(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.DictField(child=serializers.JSONField())
    current_version = serializers.IntegerField(required=False)
