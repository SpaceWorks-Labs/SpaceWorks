from django.utils.translation import gettext
from rest_framework import serializers
from apps.accounts.login_security_contract import FACTORS, PURPOSE_LOGIN, PURPOSE_RISK
from apps.accounts.schemas_auth import UserPayloadSerializer

DEVICE_TRUST_HELP = ("Native sign-ins only: keep it and send it back in the `X-Device-Trust` header on later "
                     "sign-ins, so this device is recognised by the unusual-sign-in check.")


class MFAChallengeResponseSerializer(serializers.Serializer):
    mfa_required = serializers.BooleanField()
    enrollment_required = serializers.BooleanField()
    challenge = serializers.CharField()
    expires_in = serializers.IntegerField()
    purpose = serializers.ChoiceField(
        choices=(PURPOSE_LOGIN, PURPOSE_RISK), required=False,
        help_text="`login`: a second factor (or enrolment). `risk`: an unusual sign-in; a 6-digit code was "
                  "emailed (factor `email_code`; resend with `POST auth/login-code/resend`).")
    factors = serializers.ListField(
        child=serializers.ChoiceField(choices=FACTORS), required=False,
        help_text="What this person may answer with, in this order. Empty while enrolment is required.")


class MFAChallengeSerializer(serializers.Serializer):
    challenge = serializers.CharField(min_length=20, max_length=200, write_only=True)


class MFAWebAuthnSerializer(serializers.Serializer):
    ceremony = serializers.UUIDField(help_text="From `POST auth/mfa/passkey/options`.")
    credential = serializers.JSONField(help_text="The PublicKeyCredential as JSON, as the browser returned it.")


class MFAVerifySerializer(MFAChallengeSerializer):
    code = serializers.CharField(min_length=6, max_length=64, write_only=True, trim_whitespace=True,
                                 required=False)
    factor = serializers.ChoiceField(
        choices=FACTORS, required=False, write_only=True,
        help_text="Which factor answers. Omitted: an authenticator code, then a recovery code.")
    webauthn = MFAWebAuthnSerializer(required=False, write_only=True,
                                     help_text="Required with `factor: passkey`.")

    def validate(self, attrs):
        if attrs.get("factor") == "passkey":
            if not attrs.get("webauthn"):
                raise serializers.ValidationError({"webauthn": gettext("Required for a passkey.")})
        elif not attrs.get("code"):
            raise serializers.ValidationError({"code": gettext("This field is required.")})
        return attrs


class MFAEnrollmentSerializer(serializers.Serializer):
    secret = serializers.CharField()
    provisioning_uri = serializers.CharField()
    qr_data_url = serializers.CharField()


class MFACompletedSerializer(serializers.Serializer):
    access = serializers.CharField()
    surface = serializers.CharField()
    user = UserPayloadSerializer
    refresh = serializers.CharField(required=False)
    device_grant = serializers.DictField(required=False)
    recovery_codes = serializers.ListField(child=serializers.CharField(), required=False)
    device_trust = serializers.CharField(required=False, help_text=DEVICE_TRUST_HELP)


class MFAPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=1024, write_only=True, trim_whitespace=False)


class MFAEnrollmentStartSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=1024, required=False, default="", allow_blank=True, write_only=True, trim_whitespace=False)


class MFAStatusSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    password_available = serializers.BooleanField(required=False)
    enabled = serializers.BooleanField()
    required = serializers.BooleanField()


class MFARecoverySerializer(serializers.Serializer):
    recovery_codes = serializers.ListField(child=serializers.CharField())
