"""Anonymous archive-recovery contracts never return tokens or restore authority."""

from rest_framework import serializers

from apps.accounts.serializers_phone import PhoneLoginConfirmSerializer, PhoneLoginStartSerializer
from apps.accounts.serializers_attestation import AttestationPayloadField


class AccountRestoreEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    token = serializers.CharField(max_length=512, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class AccountRestorePhoneSerializer(PhoneLoginConfirmSerializer):
    new_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class AccountRestoreSocialStartSerializer(PhoneLoginStartSerializer):
    phone = None
    username = serializers.CharField(max_length=150)
    provider = serializers.CharField(max_length=100)
    redirect_uri = serializers.URLField(max_length=1000, required=False, allow_blank=True, default="")


class AccountRestoreSocialCompleteSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=512, trim_whitespace=False, write_only=True)
    nonce = serializers.CharField(max_length=512, trim_whitespace=False, write_only=True)
    id_token = serializers.CharField(max_length=16384, required=False, default="", write_only=True)
    code = serializers.CharField(max_length=4096, required=False, default="", write_only=True)
    challenge = serializers.CharField(max_length=512, required=False, default="", write_only=True)
    attestation = AttestationPayloadField(required=False, write_only=True)


class AccountRestoreSocialResultSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()
    state = serializers.CharField()
    nonce = serializers.CharField()
    expires_in = serializers.IntegerField()


class AccountRestoreResultSerializer(serializers.Serializer):
    restored = serializers.BooleanField()
    detail = serializers.CharField()
