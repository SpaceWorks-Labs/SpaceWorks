"""Public native login discovery; credentials and verifier configuration stay private."""

from django.core.exceptions import ValidationError
from rest_framework import serializers

from apps.accounts.native_app_identity import eligible_registrations, min_app_versions, registration_signing_identities
from apps.accounts.models_attestation import PlatformAttestationSettings

from apps.accounts.login_methods import (
    password_login_enabled, phone_login_enabled, provider_login_enabled,
    social_login_enabled,
)
from apps.accounts.member_identity import member_accounts_enabled
from apps.accounts.models_oidc import enabled_providers
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.integrations.sms import sms_configured


class NativeMinVersionSerializer(serializers.Serializer):
    android = serializers.CharField(allow_null=True, help_text="Highest dotted-numeric minimum among approved global production Android registrations, or null.")
    ios = serializers.CharField(allow_null=True, help_text="Highest dotted-numeric minimum among approved global production Apple registrations, or null.")


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


class NativeAppIdentitySerializer(serializers.Serializer):
    app_id = serializers.CharField()
    signing_identities = serializers.ListField(child=serializers.CharField())


class NativeAppIdentitiesSerializer(serializers.Serializer):
    android = NativeAppIdentitySerializer(allow_null=True)
    ios = NativeAppIdentitySerializer(allow_null=True)


class NativeConfigSerializer(serializers.Serializer):
    app_display_name = serializers.CharField()
    app_identity = NativeAppIdentitiesSerializer()
    min_app_version = NativeMinVersionSerializer()
    providers = NativeProvidersSerializer()


def native_config():
    display_name = PlatformAttestationSettings.objects.filter(pk=1).values_list("app_display_name", flat=True).first()
    identities = {"android": None, "ios": None}
    for row in eligible_registrations(production=True):
        try:
            signers = registration_signing_identities(row)
        except ValidationError:
            continue  # Invalid legacy rows cannot advertise a usable app identity.
        key = "ios" if row.platform == "apple" else row.platform
        identities[key] = {"app_id": row.app_id, "signing_identities": signers}
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
        "app_display_name": display_name or "SpaceWorks",
        "app_identity": identities,
        "min_app_version": min_app_versions(),
        "providers": providers,
    }
