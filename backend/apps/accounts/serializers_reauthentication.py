from rest_framework import serializers


class ReauthenticationSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=1024, required=False, default="", allow_blank=True, write_only=True, trim_whitespace=False)
    code = serializers.CharField(max_length=6, required=False, default="", allow_blank=True, write_only=True)


class ReauthenticationResultSerializer(serializers.Serializer):
    verified = serializers.BooleanField()
    expires_in = serializers.IntegerField()
    mfa_required = serializers.BooleanField(required=False)
    factor_required = serializers.ChoiceField(choices=["totp", "phone", "email_code"], required=False)
    factor_token = serializers.CharField(required=False)


class ReauthenticationStatusSerializer(serializers.Serializer):
    verified = serializers.BooleanField()
    password_available = serializers.BooleanField()
    mfa_enabled = serializers.BooleanField()
    passkey_available = serializers.BooleanField(
        help_text="The person may re-authenticate with a passkey (reauth/passkey); with passkeys and no "
                  "authenticator, a password alone no longer re-authenticates.")
    providers = serializers.ListField(child=serializers.CharField())


class ReauthenticationSocialStartSerializer(serializers.Serializer):
    provider = serializers.CharField(max_length=64)
    redirect_uri = serializers.URLField(max_length=2048, required=False, default="", allow_blank=True)


class ReauthenticationSocialStartedSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()
    state = serializers.CharField()
    nonce = serializers.CharField()
    expires_in = serializers.IntegerField()


class ReauthenticationSocialCompleteSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=200, write_only=True)
    nonce = serializers.CharField(max_length=200, write_only=True)
    id_token = serializers.CharField(max_length=16384, required=False, default="", allow_blank=True, write_only=True)
    code = serializers.CharField(max_length=2048, required=False, default="", allow_blank=True, write_only=True)
    totp = serializers.CharField(max_length=6, required=False, default="", allow_blank=True, write_only=True)


class ReauthenticationEmailConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200, write_only=True)


class ReauthenticationEmailSentSerializer(serializers.Serializer):
    sent = serializers.BooleanField()


class ReauthenticationEmailConfirmedSerializer(serializers.Serializer):
    confirmed = serializers.BooleanField()


class EmptySerializer(serializers.Serializer):
    pass


class ReauthenticationFactorSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200, write_only=True)
    code = serializers.RegexField(r"^[0-9]{6}$", max_length=6, write_only=True)


class ReauthenticationPhoneStartedSerializer(serializers.Serializer):
    sent = serializers.BooleanField()
    token = serializers.CharField()
