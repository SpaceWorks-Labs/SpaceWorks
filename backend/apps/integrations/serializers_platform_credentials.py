"""Request and response shapes for the platform provider credentials API (#190).

The update serializers check types only; the /control/ forms behind them own the real
validation (E.164 numbers, numeric Meta ids, the service-account key, sender
reservations). A secret field is write-only: blank keeps the stored value, and
``clear_<name>`` removes it.
"""

from rest_framework import serializers


def _text(**kwargs):
    return serializers.CharField(required=False, allow_blank=True, **kwargs)


def _secret(**kwargs):
    return serializers.CharField(required=False, allow_blank=True, write_only=True, trim_whitespace=False, **kwargs)


def _flag():
    return serializers.BooleanField(required=False)


class SmsCredentialsUpdate(serializers.Serializer):
    is_enabled = _flag()
    provider = serializers.ChoiceField(choices=[("twilio", "Twilio")], required=False)
    account_sid = _text(max_length=255)
    from_number = _text(max_length=32)
    notifications_enabled = _flag()
    notifications_from_number = _text(max_length=32)
    auth_token = _secret(max_length=512)
    clear_auth_token = _flag()


class PushCredentialsUpdate(serializers.Serializer):
    apns_team_id = _text(max_length=64)
    apns_key_id = _text(max_length=64)
    apns_topic = _text(max_length=255)
    fcm_service_account = _secret(max_length=20000)
    clear_fcm_service_account = _flag()
    apns_private_key = _secret(max_length=20000)
    clear_apns_private_key = _flag()


class WhatsAppCredentialsUpdate(serializers.Serializer):
    is_enabled = _flag()
    app_id = _text(max_length=64)
    phone_number_id = _text(max_length=64)
    business_account_id = _text(max_length=64)
    access_token = _secret(max_length=8000)
    clear_access_token = _flag()
    app_secret = _secret(max_length=8000)
    clear_app_secret = _flag()


class AttestationCredentialsUpdate(serializers.Serializer):
    app_display_name = _text(max_length=100)
    play_integrity_service_account = _secret(max_length=20000)
    clear_play_integrity_service_account = _flag()


class LoginMethodsUpdate(serializers.Serializer):
    password_enabled = _flag()
    social_enabled = _flag()
    phone_enabled = _flag()
    self_registration_enabled = _flag()
    passkeys_enabled = _flag()


class _Stamp(serializers.Serializer):
    at = serializers.DateTimeField(allow_null=True)
    by = serializers.CharField(allow_null=True)


class _SecretState(serializers.Serializer):
    name = serializers.CharField()
    set = serializers.BooleanField()
    last_changed = _Stamp()


class PlatformCredentialsSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["sms", "push", "whatsapp", "attestation", "login_methods"])
    values = serializers.DictField(help_text="The readable settings, by field name.")
    secrets = _SecretState(many=True, help_text="Write-only secrets: whether each is set, never its value.")
    info = serializers.DictField(help_text="Read-only setup facts (WhatsApp: webhook verify token and callback URL).")
    updated_at = serializers.DateTimeField(allow_null=True)
    last_changed = _Stamp()
    test = serializers.ChoiceField(choices=["send", "check"], allow_null=True)


class SmsTestSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=32, help_text="The number to text, in international form (+447700900123).")

    def validate_to(self, value):
        from apps.accounts.phone_numbers import InvalidPhoneNumber, normalize_e164
        try:
            return normalize_e164(value)
        except InvalidPhoneNumber as exc:
            raise serializers.ValidationError(str(exc)) from exc
