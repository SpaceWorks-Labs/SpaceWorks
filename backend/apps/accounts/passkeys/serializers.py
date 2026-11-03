"""Request and response shapes of the passkey endpoints (OpenAPI)."""

from rest_framework import serializers

from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.schemas_auth import AuthUserPayload

_CREDENTIAL_HELP = ("The PublicKeyCredential as JSON, exactly as the browser returned it "
                    "(base64url binary fields, e.g. from @simplewebauthn/browser).")


class PasskeySerializer(serializers.ModelSerializer):
    usable_here = serializers.SerializerMethodField(
        help_text="Registered on this address's relying-party ID; others still count as a factor but "
                  "only work on the address they were created on.")

    class Meta:
        model = WebAuthnCredential
        fields = ("id", "name", "rp_id", "transports", "backed_up", "created_at", "last_used_at", "usable_here")
        read_only_fields = fields

    def get_usable_here(self, obj) -> bool:
        return obj.rp_id == self.context.get("rp_id")


class PasskeyListSerializer(serializers.Serializer):
    passkeys = PasskeySerializer(many=True)
    passkeys_allowed = serializers.BooleanField(
        help_text="False when the platform switch or a staff space's security.passkeys_allowed turns them off.")
    rp_id = serializers.CharField(allow_null=True, help_text="This address's relying-party ID, if it has one.")


class PasskeyRenameSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, allow_blank=True)


class PasskeyOptionsSerializer(serializers.Serializer):
    ceremony = serializers.UUIDField(help_text="Send back with the browser's answer; valid once, for 5 minutes.")
    options = serializers.JSONField(help_text="publicKey options for navigator.credentials.create()/get().")


class PasskeyMfaOptionsRequestSerializer(serializers.Serializer):
    challenge = serializers.CharField(max_length=128, help_text="The MFA challenge from the login response.")


class PasskeyVerifyRequestSerializer(serializers.Serializer):
    ceremony = serializers.UUIDField()
    credential = serializers.JSONField(help_text=_CREDENTIAL_HELP)


class PasskeyRegisterRequestSerializer(PasskeyVerifyRequestSerializer):
    name = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class PasskeyRegisteredSerializer(serializers.Serializer):
    passkey = PasskeySerializer()
    recovery_codes = serializers.ListField(
        child=serializers.CharField(), allow_null=True,
        help_text="Shown once when the account had no recovery codes yet; null otherwise.")
    access = serializers.CharField(help_text="A fresh session: every other session ended with this change.")
    surface = serializers.CharField()
    user = AuthUserPayload()


class PasskeyRemovedSerializer(serializers.Serializer):
    signed_out = serializers.BooleanField(
        help_text="True when this session's proof was the removed factor: sign in again.")
    access = serializers.CharField(required=False)
    surface = serializers.CharField(required=False)
    user = AuthUserPayload(required=False)


class PasskeyLoginSerializer(serializers.Serializer):
    access = serializers.CharField()
    surface = serializers.ChoiceField(choices=("member", "verification_only"))
    user = AuthUserPayload()


class PasskeyReauthenticatedSerializer(serializers.Serializer):
    verified = serializers.BooleanField()
    expires_in = serializers.IntegerField()
