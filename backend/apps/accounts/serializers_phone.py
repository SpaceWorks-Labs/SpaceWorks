from django.utils.translation import gettext
from rest_framework import serializers

from apps.accounts.models_social import SocialClientPlatform, SocialDelivery
from apps.accounts.serializers_attestation import AttestationPayloadField
from apps.accounts.serializers_device import APP_VERSION_HELP


class PhoneStartSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)


class PhoneConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    # Not an IntegerField: a code is a fixed-length digit string, and "012345" must not
    # be coerced to 12345 and then fail to match its own digest.
    code = serializers.CharField(min_length=6, max_length=6)


class PhoneLoginStartSerializer(PhoneStartSerializer):
    delivery = serializers.ChoiceField(choices=SocialDelivery.choices, default="web")
    client_platform = serializers.ChoiceField(
        choices=SocialClientPlatform.choices, default="web",
    )
    challenge = serializers.CharField(
        max_length=512, required=False, write_only=True, trim_whitespace=False,
    )

    def validate(self, attrs):
        device = attrs["delivery"] == "device"
        if device == (attrs["client_platform"] == "web"):
            raise serializers.ValidationError(gettext("Invalid phone delivery platform."))
        if device != bool(attrs.get("challenge")):
            raise serializers.ValidationError(
                gettext("Only device delivery requires an attestation challenge.")
            )
        return attrs


class PhoneLoginConfirmSerializer(PhoneLoginStartSerializer, PhoneConfirmSerializer):
    attestation = AttestationPayloadField(required=False, write_only=True)
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["delivery"] == "device":
            value = attrs.get("attestation")
            if not isinstance(value, dict) or not value or len(value) > 16:
                raise serializers.ValidationError({"attestation": gettext("Invalid attestation payload.")})
        elif "attestation" in attrs:
            raise serializers.ValidationError(gettext("Web phone login cannot use attestation."))
        return attrs


class PhoneStartResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PhoneStatusSerializer(serializers.Serializer):
    phone_e164 = serializers.CharField(allow_blank=True)
    verified = serializers.BooleanField()
