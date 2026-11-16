"""Explicit read/write contracts: ciphertext and provider tokens never serialize."""
from rest_framework import serializers

from apps.accounts.phone_numbers import InvalidPhoneNumber, normalize_e164
from apps.integrations.models import WhatsAppTemplateBinding
from .templates import validate_binding


class StrictInput:
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - {key for key, field in self.fields.items() if not field.read_only}
            if unknown:
                raise serializers.ValidationError({key: "Unsupported or read-only field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class MessagingSettingsSerializer(StrictInput, serializers.Serializer):
    use_platform_sender = serializers.BooleanField(required=False)
    sms_account_sid = serializers.RegexField(r"^(AC[0-9a-fA-F]{32})?$", required=False, allow_blank=True)
    sms_from_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    sms_auth_token = serializers.CharField(max_length=4096, write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    whatsapp_phone_number_id = serializers.RegexField(r"^\d{1,64}$", required=False, allow_blank=True)
    whatsapp_business_account_id = serializers.RegexField(r"^\d{1,64}$", required=False, allow_blank=True)
    whatsapp_access_token = serializers.CharField(max_length=8192, write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    whatsapp_app_secret = serializers.CharField(max_length=4096, write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    sms_auth_token_set = serializers.BooleanField(read_only=True)
    whatsapp_access_token_set = serializers.BooleanField(read_only=True)
    whatsapp_app_secret_set = serializers.BooleanField(read_only=True)
    whatsapp_webhook_verify_token = serializers.CharField(read_only=True)
    effective_source = serializers.DictField(child=serializers.ChoiceField(choices=["own", "platform", "none"]), read_only=True)
    platform_available = serializers.DictField(child=serializers.BooleanField(), read_only=True)
    webhook_urls = serializers.DictField(child=serializers.DictField(child=serializers.CharField()), read_only=True)

    def validate_sms_from_number(self, value):
        if not value:
            return ""
        try:
            return normalize_e164(value)
        except InvalidPhoneNumber as exc:
            raise serializers.ValidationError(str(exc)) from exc


class WhatsAppBindingSerializer(StrictInput, serializers.ModelSerializer):
    components = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = WhatsAppTemplateBinding
        fields = ("id", "feature", "event", "audience", "business_account_id", "template_name", "language",
                  "parameters", "is_active", "needs_review", "components")
        read_only_fields = ("id", "business_account_id", "needs_review")
        validators = []

    def validate(self, values):
        return validate_binding(values, self.instance)


class ConsentWriteSerializer(StrictInput, serializers.Serializer):
    makerspace = serializers.IntegerField(min_value=1)
    channel = serializers.ChoiceField(choices=["sms", "whatsapp"])
    action = serializers.ChoiceField(choices=["opted_in", "opted_out"])


class MessagingChannelSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    consented = serializers.BooleanField()
    phone_verified = serializers.BooleanField()
    phone_masked = serializers.CharField()
    suppressed = serializers.BooleanField()


class MemberMessagingSerializer(serializers.Serializer):
    sms = MessagingChannelSerializer()
    whatsapp = MessagingChannelSerializer()


class MessagingCatalogEntrySerializer(serializers.Serializer):
    feature = serializers.CharField()
    event = serializers.CharField()
    audience = serializers.ChoiceField(choices=["member", "staff"])
    allowed_projection_keys = serializers.ListField(child=serializers.CharField())
    supported_languages = serializers.ListField(child=serializers.CharField())


class WhatsAppBindingPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = WhatsAppBindingSerializer(many=True)
