from django.utils.translation import gettext
from rest_framework import serializers

from apps.accounts.models_devices import DeviceEnvironment, DevicePlatform
from apps.accounts.serializers_attestation import AttestationPayloadField


class DeviceIdentitySerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=DevicePlatform.choices)
    app_id = serializers.RegexField(r"^[A-Za-z0-9._-]{3,255}$", max_length=255)
    environment = serializers.ChoiceField(choices=DeviceEnvironment.choices)


APP_VERSION_HELP = ("The app's own version (x.y.z). Refused with 426 native_app_update_required when it is "
                    "older than the deployment's minimum for this platform, or missing while a minimum is set.")


class DeviceLoginSerializer(DeviceIdentitySerializer):
    authority = serializers.ChoiceField(
        choices=("member", "staff"), default="member",
        help_text="member (default) or staff: a step-up fixed to one makerspace where the person holds a "
                  "staff role. Staff always needs the authenticator (or enrolment) and attestation.",
    )
    makerspace = serializers.SlugField(required=False, max_length=150,
                                       help_text="The staff makerspace's slug; required for authority=staff only.")
    username = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=1024, write_only=True, trim_whitespace=False)
    challenge = serializers.CharField(max_length=512, trim_whitespace=False)
    attestation = AttestationPayloadField()
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)

    def validate_attestation(self, value):
        if not isinstance(value, dict) or not value or len(value) > 16:
            raise serializers.ValidationError(gettext("Invalid attestation payload."))
        return value

    def validate(self, attrs):
        if attrs["authority"] == "staff" and not attrs.get("makerspace"):
            raise serializers.ValidationError({"makerspace": gettext("This field is required for a staff grant.")})
        if attrs["authority"] != "staff" and attrs.get("makerspace"):
            raise serializers.ValidationError({"makerspace": gettext("Use a makerspace only for a staff grant.")})
        return attrs


class DeviceStaffGrantSerializer(serializers.Serializer):
    """Step up an active device session of this person to a staff grant (Q12)."""
    makerspace = serializers.SlugField(max_length=150, help_text="The makerspace the staff grant is fixed to.")
    challenge = serializers.CharField(max_length=512, trim_whitespace=False,
                                      help_text="A fresh attestation challenge for this device's app.")
    attestation = AttestationPayloadField()
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)

    def validate_attestation(self, value):
        if not isinstance(value, dict) or not value or len(value) > 16:
            raise serializers.ValidationError(gettext("Invalid attestation payload."))
        return value


class DeviceEventGrantSerializer(serializers.Serializer):
    """Step up an active device session of this person to an event-role grant (#173)."""
    event_id = serializers.IntegerField(min_value=1, help_text="The one event the grant is limited to.")
    challenge = serializers.CharField(max_length=512, trim_whitespace=False,
                                      help_text="A fresh attestation challenge for this device's app.")
    attestation = AttestationPayloadField()
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)

    def validate_attestation(self, value):
        if not isinstance(value, dict) or not value or len(value) > 16:
            raise serializers.ValidationError(gettext("Invalid attestation payload."))
        return value


class DeviceRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=4096, write_only=True, trim_whitespace=False)
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)


class DeviceGrantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=DevicePlatform.choices)
    app_id = serializers.CharField()
    environment = serializers.CharField()
    status = serializers.CharField()
    authority = serializers.ChoiceField(choices=("member", "staff", "event"))
    staff_makerspace_id = serializers.IntegerField(allow_null=True)
    event_id = serializers.IntegerField(allow_null=True, required=False,
                                        help_text="The one event an event-role grant is limited to (#173).")
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
    device_trust = serializers.CharField(
        required=False, allow_null=True,
        help_text="Keep it and send it back in the `X-Device-Trust` header on later sign-ins, so this "
                  "device is recognised by the unusual-sign-in check (S-B).")


class DeviceChallengeResponseSerializer(serializers.Serializer):
    challenge = serializers.CharField()
    expires_in = serializers.IntegerField(min_value=1)


class DeviceRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    device_grant = DeviceGrantSerializer()


class DeviceLogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
