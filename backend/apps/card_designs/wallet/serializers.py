"""Request and response shapes for wallet credentials and guest-pass wallet links.

Secrets exist only on the INPUT serializer; no response serializer has a field that can carry
one, so a credential cannot be returned even by mistake.
"""
from rest_framework import serializers

_BIG = {"required": False, "allow_blank": True, "trim_whitespace": False, "max_length": 100_000, "write_only": True}


class WalletCredentialsInputSerializer(serializers.Serializer):
    """Every secret is write-only. Send only the groups to change; stored secrets the request omits are kept."""
    apple_pass_type_id = serializers.CharField(required=False, allow_blank=True, max_length=120)
    apple_team_id = serializers.CharField(required=False, allow_blank=True, max_length=20)
    apple_p12 = serializers.CharField(help_text="Base64 of the .p12 export of the Pass Type ID certificate.", **_BIG)
    apple_p12_password = serializers.CharField(**{**_BIG, "max_length": 256})
    apple_cert_pem = serializers.CharField(**_BIG)
    apple_key_pem = serializers.CharField(**_BIG)
    apple_key_passphrase = serializers.CharField(**{**_BIG, "max_length": 256})
    apple_wwdr_pem = serializers.CharField(**_BIG)
    google_issuer_id = serializers.CharField(required=False, allow_blank=True, max_length=32)
    google_class_prefix = serializers.CharField(required=False, allow_blank=True, max_length=40)
    google_service_account = serializers.CharField(help_text="The service-account JSON key file contents.", **_BIG)
    clear_apple = serializers.BooleanField(required=False, default=False)
    clear_google = serializers.BooleanField(required=False, default=False)
    use_platform_credentials = serializers.BooleanField(
        required=False, help_text="Per-space routes only (decision 281): may the platform's certificates sign this "
                                  "space's passes when it has none of its own? Default true; false = no platform fallback.")


class AppleStatusSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    pass_type_id = serializers.CharField(required=False)
    team_id = serializers.CharField(required=False)
    fingerprint = serializers.CharField(required=False, help_text="SHA-256 of the signing certificate, hex.")
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_soon = serializers.BooleanField(required=False)


class GoogleStatusSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    issuer_id = serializers.CharField(required=False)
    class_prefix = serializers.CharField(required=False)
    fingerprint = serializers.CharField(required=False, help_text="SHA-256 of the service-account public key, hex.")


class EffectiveSourceSerializer(serializers.Serializer):
    apple = serializers.ChoiceField(choices=("space", "platform", "deployment"), allow_null=True)
    google = serializers.ChoiceField(choices=("space", "platform", "deployment"), allow_null=True)


class WalletCredentialsSerializer(serializers.Serializer):
    apple = AppleStatusSerializer()
    google = GoogleStatusSerializer()
    reissue_needed = serializers.BooleanField(required=False, help_text=(
        "Save responses only. True when the Apple Pass Type ID changed: passes already in wallets no "
        "longer verify, so holders re-add them from My passes."))


class SpaceWalletCredentialsSerializer(WalletCredentialsSerializer):
    use_platform_credentials = serializers.BooleanField(
        help_text="Decision 281: the platform's certificates may sign this space's passes when it has none.")
    effective = EffectiveSourceSerializer(
        help_text="Which credentials sign this space's passes: its own, the platform's, or null (wallet off).")


class GuestPassWalletSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=("apple", "google"))
    url = serializers.CharField(help_text="Apple: a one-minute .pkpass download link. Google: the Save to Google "
                                          "Wallet link.")
    expires_in = serializers.IntegerField(allow_null=True)


class GuestPassScanInputSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class GuestPassScanResultSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True, help_text="`expired`, `revoked`, `converted`, `not_yet_valid` "
                                                               "or `unknown` when not valid.")
    pass_id = serializers.IntegerField(allow_null=True)
    holder_name = serializers.CharField(allow_blank=True)
    kind = serializers.CharField(allow_blank=True)
    valid_until = serializers.DateTimeField(allow_null=True)
    entitlements = serializers.DictField()
