"""Raw v2 metadata at HTTP boundaries; canonical snapshots stay server-owned."""
from rest_framework import serializers


class RegistrationFormInput(serializers.Serializer):
    custom_answers = serializers.JSONField(required=False, allow_null=True, write_only=True)
    answers = serializers.JSONField(required=False, allow_null=True, write_only=True)
    form = serializers.JSONField(required=False, write_only=True)
    operation_id = serializers.UUIDField(required=False, write_only=True)
    derivations = serializers.JSONField(required=False, write_only=True)
    save_choices = serializers.JSONField(required=False, write_only=True)
    saved_detail_versions = serializers.JSONField(required=False, write_only=True)
    event_date_revision = serializers.IntegerField(required=False, min_value=1, write_only=True)

    def validate(self, attrs):
        schema = self.context.get("event").custom_form if self.context.get("event") else None
        return normalize_form_attrs(attrs, schema=schema)


def normalize_form_attrs(attrs, *, schema):
    if "answers" in attrs and "custom_answers" in attrs:
        raise serializers.ValidationError({"code": "answer_field_conflict"})
    keys = ("answers", "form", "operation_id", "derivations", "save_choices", "saved_detail_versions", "event_date_revision")
    if not (isinstance(schema, dict) and schema.get("schema_version") == 2):
        if any(key in attrs for key in ("answers", "form", "derivations", "save_choices", "saved_detail_versions")):
            raise serializers.ValidationError({"code": "invalid_form_input"})
        attrs.pop("operation_id", None)
        attrs.pop("event_date_revision", None)
        return attrs
    if isinstance(schema, dict) and schema.get("schema_version") == 2:
        attrs["form_payload"] = {key: attrs.pop(key) for key in keys if key in attrs}
        if "custom_answers" in attrs:
            attrs["form_payload"]["answers"] = attrs.pop("custom_answers")
    return attrs
