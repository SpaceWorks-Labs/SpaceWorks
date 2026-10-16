"""Public native login discovery; credentials and verifier configuration stay private."""

from django.conf import settings
from rest_framework import serializers

from apps.accounts.login_methods import (
    password_login_enabled, phone_login_enabled, provider_login_enabled,
    social_login_enabled,
)
from apps.accounts.member_identity import member_accounts_enabled
from apps.accounts.models_oidc import enabled_providers
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.integrations.sms import sms_configured


class NativeMinVersionSerializer(serializers.Serializer):
    android = serializers.CharField(allow_null=True)
    ios = serializers.CharField(allow_null=True)


class NativeGoogleSerializer(serializers.Serializer):
    android_client_id = serializers.CharField(allow_blank=True)
    ios_client_id = serializers.CharField(allow_blank=True)


class NativeAppleSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class NativeOidcSerializer(serializers.Serializer):
    key = serializers.CharField()
    display_name = serializers.CharField()
    client_id = serializers.CharField()
    issuer = serializers.CharField()


class NativeProvidersSerializer(serializers.Serializer):
    password = serializers.BooleanField()
    phone = serializers.BooleanField()
    google = NativeGoogleSerializer(allow_null=True)
    apple = NativeAppleSerializer(allow_null=True)
    oidc = NativeOidcSerializer(many=True)


class NativeConfigSerializer(serializers.Serializer):
    min_app_version = NativeMinVersionSerializer()
    providers = NativeProvidersSerializer()


def native_config():
    providers = {
        "password": password_login_enabled(),
        "phone": bool(member_accounts_enabled() and phone_login_enabled() and sms_configured()),
        "google": None,
        "apple": None,
        "oidc": [],
    }
    if social_login_enabled():
        social = PlatformSocialAuthSettings.objects.filter(pk=1).first()
        if provider_login_enabled("google") and social and (
            social.google_android_client_id or social.google_ios_client_id
        ):
            providers["google"] = {
                "android_client_id": social.google_android_client_id,
                "ios_client_id": social.google_ios_client_id,
            }
        if provider_login_enabled("apple") and social and any(
            isinstance(app_id, str) and app_id for app_id in social.apple_native_app_ids
        ):
            providers["apple"] = {"enabled": True}
        providers["oidc"] = [
            {"key": row.provider_key, "display_name": row.display_name,
             "client_id": row.client_id, "issuer": row.issuer}
            for row in enabled_providers() if provider_login_enabled(row.provider_key)
        ]
    return {
        "min_app_version": {
            "android": settings.MOBILE_MIN_VERSION_ANDROID or None,
            "ios": settings.MOBILE_MIN_VERSION_IOS or None,
        },
        "providers": providers,
    }
