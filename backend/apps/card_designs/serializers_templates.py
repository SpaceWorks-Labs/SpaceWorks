"""Shapes for the card-template routes (documentation serializers for responses; request serializers validate)."""
from django.utils.translation import gettext
from rest_framework import serializers

from .serializers import CardDesignSerializer


class TemplateRowSerializer(serializers.Serializer):
    id = serializers.JSONField(help_text='A number for a space template, "builtin:<key>:<theme>" for a built-in.')
    source = serializers.ChoiceField(choices=("space", "builtin"))
    key = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    kind = serializers.ChoiceField(choices=("card", "certificate"))
    domain_hint = serializers.CharField(allow_blank=True)
    stock = serializers.CharField()
    theme = serializers.ChoiceField(choices=("light", "dark"))
    orientation = serializers.ChoiceField(choices=("portrait", "landscape"))
    back_enabled = serializers.BooleanField()
    updated_at = serializers.DateTimeField(allow_null=True)


class TemplateDetailSerializer(TemplateRowSerializer):
    document = serializers.JSONField(help_text="The version 3 card design document.")


class TemplateCreateSerializer(serializers.Serializer):
    design_id = serializers.IntegerField(min_value=1, required=False,
                                         help_text="Save this card design as a template. Send this or `document`.")
    document = serializers.JSONField(required=False, help_text=(
        "Save a certificate document (kind certificate, version 3, no images) as a template. Send this or `design_id`."))
    name = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate(self, data):
        if ("design_id" in data) == ("document" in data):
            raise serializers.ValidationError(gettext("Send either design_id or document."))
        return data


class TemplateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    description = serializers.CharField(max_length=200, required=False, allow_blank=True)
    document = serializers.JSONField(required=False)


class TemplateImportSerializer(serializers.Serializer):
    file = serializers.JSONField(help_text='A template file: {"format": "spaceworks.card-template", "format_version": 1, ...}.')


class TemplateFileSerializer(serializers.Serializer):
    format = serializers.CharField()
    format_version = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    kind = serializers.CharField()
    domain_hint = serializers.CharField(allow_blank=True)
    document = serializers.JSONField(help_text='Asset ids are "ref:<n>".')
    assets = serializers.ListField(child=serializers.DictField())


class TemplateApplySerializer(serializers.Serializer):
    template = serializers.JSONField(help_text='A space template id, or "builtin:<key>" / "builtin:<key>:<theme>".')
    expected_revision = serializers.IntegerField(min_value=1)
    keep_fields = serializers.BooleanField(default=True)
    theme = serializers.ChoiceField(choices=("light", "dark"), default="light")


class TemplateAppliedSerializer(serializers.Serializer):
    design = CardDesignSerializer()
    unplaced_fields = serializers.ListField(child=serializers.CharField(),
                                            help_text="Data fields the old design bound that the template lacked; they were appended.")
