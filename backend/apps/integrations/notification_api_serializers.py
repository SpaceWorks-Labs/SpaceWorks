"""Frozen Phase-1a HTTP shapes; credentials and destinations are never readable."""
from collections.abc import Mapping
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer

from .models_contract import NotificationDelivery
from .models_endpoints import ChannelConfiguration, NotificationEndpoint, PERSONAL_CHAT_CHANNELS, WhatsAppTemplate
from .notification_enums import NotificationChannel, NotificationFeature


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unknown field." for key in unknown})
        return super().to_internal_value(data)


@extend_schema_serializer(component_name="ContractWhatsAppTemplate")
class TemplateSerializer(serializers.ModelSerializer):
    audience = serializers.ChoiceField(choices=["staff", "requester", "member"])
    template_name = serializers.RegexField(r"^[A-Za-z0-9_.:-]{1,255}$")
    variables = serializers.ListField(child=serializers.CharField(max_length=64), max_length=30)

    class Meta:
        model = WhatsAppTemplate
        fields = ["event", "audience", "locale", "template_name", "variables", "approved"]
        extra_kwargs = {"audience": {"required": True}, "approved": {"read_only": True}}


@extend_schema_serializer(component_name="ContractChannel")
class ChannelSerializer(serializers.ModelSerializer):
    credentials_set = serializers.SerializerMethodField()
    templates = TemplateSerializer(many=True, read_only=True)

    def get_credentials_set(self, obj) -> bool:
        return bool(obj.credentials)

    class Meta:
        model = ChannelConfiguration
        fields = ["channel", "enabled", "room_enabled", "personal_enabled", "provider", "email_fallback",
                  "integration_identity", "generation", "quotas", "credentials_set", "templates"]


@extend_schema_serializer(component_name="ContractQuota")
class QuotaSerializer(StrictSerializer):
    daily_limit = serializers.IntegerField(min_value=1, max_value=100000, required=False)
    recipient_daily_limit = serializers.IntegerField(min_value=1, max_value=10000, required=False)


@extend_schema_serializer(component_name="ContractChannelPatch")
class ChannelPatchSerializer(StrictSerializer):
    enabled = serializers.BooleanField(required=False)
    room_enabled = serializers.BooleanField(required=False)
    personal_enabled = serializers.BooleanField(required=False)
    email_fallback = serializers.BooleanField(required=False)
    provider = serializers.ChoiceField(choices=["telegram", "slack", "mattermost", "discord", "twilio", "meta", "builtin", "webhook"], required=False)
    integration_identity = serializers.CharField(max_length=255, required=False)
    credentials = serializers.DictField(child=serializers.CharField(max_length=8000), required=False, write_only=True)
    quotas = QuotaSerializer(required=False)
    templates = TemplateSerializer(many=True, required=False)

    def validate_credentials(self, value):
        if len(value) > 20 or any(len(key) > 64 for key in value):
            raise serializers.ValidationError("At most 20 credential fields with names up to 64 characters.")
        return value

    def validate_templates(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("At most 100 template bindings.")
        identities = [(v["event"], v["audience"], v.get("locale", "en")) for v in value]
        if len(set(identities)) != len(identities):
            raise serializers.ValidationError("Duplicate template binding.")
        return value


@extend_schema_serializer(component_name="ContractEndpoint")
class EndpointSerializer(serializers.ModelSerializer):
    effective_valid = serializers.SerializerMethodField()

    def get_effective_valid(self, obj) -> bool:
        from .notification_resolution import endpoint_current
        return endpoint_current(obj)

    class Meta:
        model = NotificationEndpoint
        fields = ["id", "channel", "provider", "integration_generation", "verification_state", "verified_at",
                  "consented_at", "consent_version", "revoked_at", "created_at", "effective_valid"]


@extend_schema_serializer(component_name="ContractChannelPage")
class ChannelPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ChannelSerializer(many=True)


class OAuthReturnSerializer(serializers.Serializer):
    challenge_id = serializers.IntegerField()
    expires_at = serializers.DateTimeField()


@extend_schema_serializer(component_name="ContractEndpointPage")
class EndpointPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = EndpointSerializer(many=True)
    oauth_return = OAuthReturnSerializer(read_only=True, required=False)


@extend_schema_serializer(component_name="ContractChallengeStart")
class ChallengeStartSerializer(StrictSerializer):
    channel = serializers.ChoiceField(choices=PERSONAL_CHAT_CHANNELS)
    consent = serializers.BooleanField()
    consent_version = serializers.CharField(max_length=32)
    phone_number = serializers.RegexField(r"^\+[1-9][0-9]{6,14}$", required=False, write_only=True)

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Explicit messaging consent is required.")
        return value


@extend_schema_serializer(component_name="ContractChallenge")
class ChallengeSerializer(serializers.Serializer):
    challenge_id = serializers.IntegerField()
    expires_at = serializers.DateTimeField()
    connect_url = serializers.URLField(required=False)
    instructions = serializers.CharField(required=False)
    oauth_state = serializers.CharField(required=False)


@extend_schema_serializer(component_name="ContractProofVerify")
class ProofVerifySerializer(StrictSerializer):
    # Opaque signed/OAuth response for provider verifier. Never accepts destination ids.
    code = serializers.CharField(max_length=2048, required=False)
    state = serializers.CharField(max_length=512, required=False)


@extend_schema_serializer(component_name="ContractSelection")
class SelectionSerializer(StrictSerializer):
    category = serializers.ChoiceField(choices=NotificationFeature.values)
    channels = serializers.ListField(child=serializers.ChoiceField(choices=[c for c in NotificationChannel.values if c != "webhook"]), max_length=8)
    email_fallback = serializers.BooleanField(default=True)
    available_channels = serializers.ListField(child=serializers.CharField(), read_only=True)

    def validate_channels(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate channel.")
        return value


@extend_schema_serializer(component_name="ContractPreferences")
class PreferencesSerializer(StrictSerializer):
    preferences = SelectionSerializer(many=True)

    def validate_preferences(self, value):
        if len(value) > len(NotificationFeature.values) or len({p["category"] for p in value}) != len(value):
            raise serializers.ValidationError("Duplicate or too many categories.")
        return value


class ContractDeliverySerializer(serializers.ModelSerializer):
    envelope_id = serializers.IntegerField(read_only=True)
    event = serializers.CharField(source="envelope.event")
    feature = serializers.CharField(source="envelope.feature")

    class Meta:
        model = NotificationDelivery
        fields = ["id", "envelope_id", "channel", "state", "attempt_count", "next_attempt_at", "last_error",
                  "retryable", "event", "feature", "created_at", "updated_at"]


@extend_schema_serializer(component_name="ContractDeliveryPage")
class DeliveryPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ContractDeliverySerializer(many=True)


class ContractTestSerializer(StrictSerializer):
    channel = serializers.ChoiceField(choices=NotificationChannel.values)
    endpoint_id = serializers.IntegerField(min_value=1, required=False)
    room_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if bool(attrs.get("endpoint_id")) == bool(attrs.get("room_id")):
            raise serializers.ValidationError("Choose exactly one endpoint or room.")
        return attrs


@extend_schema_serializer(component_name="ContractProviderResult")
class ProviderResultSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    provider_id = serializers.CharField()
    retryable = serializers.BooleanField()
    error_code = serializers.CharField()
    sanitized_error = serializers.CharField()


@extend_schema_serializer(component_name="ContractRevoked")
class RevokedSerializer(serializers.Serializer):
    revoked = serializers.BooleanField()
