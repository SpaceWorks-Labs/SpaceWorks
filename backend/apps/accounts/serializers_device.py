from rest_framework import serializers

from apps.accounts.models_devices import DeviceEnvironment, DevicePlatform
from apps.accounts.serializers_attestation import AttestationPayloadField


class DeviceIdentitySerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=DevicePlatform.choices)
    app_id = serializers.RegexField(r"^[A-Za-z0-9._-]{3,255}$", max_length=255)
    environment = serializers.ChoiceField(choices=DeviceEnvironment.choices)


class DeviceLoginSerializer(DeviceIdentitySerializer):
    context = serializers.ChoiceField(choices=("member", "staff", "platform"), default="member")
    makerspace = serializers.SlugField(required=False, max_length=150)
    username = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=1024, write_only=True, trim_whitespace=False)
    challenge = serializers.CharField(max_length=512, trim_whitespace=False)
    attestation = AttestationPayloadField()

    def validate_attestation(self, value):
        if not isinstance(value, dict) or not value or len(value) > 16:
            raise serializers.ValidationError("Invalid attestation payload.")
        return value

    def validate(self, attrs):
        if attrs["context"] == "staff" and not attrs.get("makerspace"):
            raise serializers.ValidationError({"makerspace": "This field is required for staff sign-in."})
        if attrs["context"] != "staff" and attrs.get("makerspace"):
            raise serializers.ValidationError({"makerspace": "Use a makerspace only for staff sign-in."})
        return attrs


class DeviceRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=4096, write_only=True, trim_whitespace=False)


class DeviceGrantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=DevicePlatform.choices)
    app_id = serializers.CharField()
    environment = serializers.CharField()
    status = serializers.CharField()
    authority = serializers.ChoiceField(choices=("member", "staff"))
    staff_makerspace_id = serializers.IntegerField(allow_null=True)
    login_method = serializers.CharField()
    attested_at = serializers.DateTimeField()
    last_used_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()


class DeviceGrantPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = DeviceGrantSerializer(many=True)


class DeviceTokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.DictField()
    device_grant = DeviceGrantSerializer()


class DeviceChallengeResponseSerializer(serializers.Serializer):
    challenge = serializers.CharField()
    expires_in = serializers.IntegerField(min_value=1)


class DeviceRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    device_grant = DeviceGrantSerializer()


class DeviceLogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
