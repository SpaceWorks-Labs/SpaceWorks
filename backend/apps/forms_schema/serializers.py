from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.forms_schema.validation import validate_answers, validate_form_schema
from .openapi import EDITOR_FORM_SCHEMA, VERSIONED_FORM_SCHEMA


@extend_schema_field(VERSIONED_FORM_SCHEMA)
class CustomFormSchemaField(serializers.JSONField):
    def __init__(self, *args, form_context=None, **kwargs):
        self.form_context = form_context
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return validate_form_schema(value, context=self.form_context)
        except DjangoValidationError as exc:
            if self.form_context is None:
                raise serializers.ValidationError(exc.messages) from exc
            raise serializers.ValidationError({"code": getattr(exc, "code", None) or "invalid_form_schema",
                                                "detail": exc.messages}) from exc


@extend_schema_field(EDITOR_FORM_SCHEMA)
class FormEditorDocumentField(serializers.JSONField):
    """Editor commands validate in the service to preserve typed schema errors."""


class CustomFormSubmissionMixin(metaclass=serializers.SerializerMetaclass):
    custom_answers = serializers.JSONField(
        allow_null=True,
        required=False,
        write_only=True,
    )

    def custom_form_schema(self):
        raise NotImplementedError

    def custom_form_context(self):
        return None

    def custom_file_resolver(self, **kwargs):
        return False

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs['custom_answers'] = validate_answers(
            self.custom_form_schema(), attrs.get('custom_answers'), context=self.custom_form_context(),
            file_resolver=self.custom_file_resolver,
        )
        return attrs
