"""Request and response shapes of the native GitHub exchange (decision 358 A)."""

from django.utils.translation import gettext
from rest_framework import serializers

from apps.accounts.serializers_attestation import AttestationPayloadField
from apps.accounts.serializers_device import APP_VERSION_HELP

_NATIVE_PLATFORMS = (("ios", "iOS"), ("android", "Android"))
# RFC 7636: a verifier is 43-128 unreserved characters; an S256 challenge is 43 base64url ones.
_VERIFIER = r"^[A-Za-z0-9\-._~]{43,128}$"
_CHALLENGE = r"^[A-Za-z0-9_-]{43}$"


def _first_grant_rule(request, challenge, attestation=None, *, needs_attestation):
    grant = getattr(request, "device_grant", None)
    if needs_attestation and bool(challenge) != bool(attestation):
        raise serializers.ValidationError(gettext("The challenge and attestation must be presented together."))
    if (grant is None) != bool(challenge):
        raise serializers.ValidationError(gettext("A first device login requires an attestation challenge."))


class GithubNativeStartSerializer(serializers.Serializer):
    client_platform = serializers.ChoiceField(choices=_NATIVE_PLATFORMS)
    code_challenge = serializers.RegexField(
        _CHALLENGE, help_text="base64url(SHA-256(code_verifier)) without padding; the app keeps the verifier.")
    code_challenge_method = serializers.ChoiceField(choices=(("S256", "S256"),), default="S256")
    challenge = serializers.CharField(
        max_length=512, required=False, write_only=True, trim_whitespace=False,
        help_text="An unspent attestation challenge; required for a first grant, omitted with a device bearer.")

    def validate(self, attrs):
        _first_grant_rule(self.context.get("request"), attrs.get("challenge"), needs_attestation=False)
        return attrs


class GithubNativeStartResponseSerializer(serializers.Serializer):
    authorization_url = serializers.URLField(help_text="Open in the system browser / ASWebAuthenticationSession.")
    state = serializers.CharField(help_text="One-time; GitHub returns it on the app link with the code.")
    redirect_uri = serializers.URLField(help_text="The app link GitHub redirects to (claimed by the association files).")
    expires_in = serializers.IntegerField()


class GithubNativeExchangeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=512, write_only=True, trim_whitespace=False)
    state = serializers.CharField(max_length=512, write_only=True, trim_whitespace=False)
    code_verifier = serializers.RegexField(_VERIFIER, write_only=True)
    client_platform = serializers.ChoiceField(choices=_NATIVE_PLATFORMS)
    challenge = serializers.CharField(max_length=512, required=False, write_only=True, trim_whitespace=False)
    attestation = AttestationPayloadField(required=False, write_only=True)
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)

    def validate_attestation(self, value):
        if not isinstance(value, dict) or not value or len(value) > 16:
            raise serializers.ValidationError(gettext("Invalid attestation payload."))
        return value

    def validate(self, attrs):
        _first_grant_rule(self.context.get("request"), attrs.get("challenge"), attrs.get("attestation"),
                          needs_attestation=True)
        return attrs
