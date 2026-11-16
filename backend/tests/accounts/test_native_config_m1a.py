"""Native discovery follows deployment switches and the attested Apple app ID."""

from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import DeviceGrant, PlatformLoginMethods
from apps.accounts.models_social import PlatformSocialAuthSettings
from tests.accounts.mobile_integration_helpers import APP, FIRST, SECOND, PREFIX, registration
from tests.accounts.native_helpers_m1d import configure_native_social, mock_attestation
from tests.accounts.oidc_browser_helpers import make_provider
from tests.accounts.test_phone_auth_p8 import sms_on
from tests.accounts.test_social_first_grant import (
    APP_ID, NONCE_URL, issue_challenge,
    mock_identity,
)
from tests.module_helpers import disable_module
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
CONFIG = "/api/v1/config"


def test_native_config_omitted_when_no_live_makerspace_can_mint_grants():
    spaces = [make_space("native-disabled-one"), make_space("native-disabled-two")]
    for space in spaces:
        disable_module(space, "mobile")
    result = APIClient().get(CONFIG)
    assert result.status_code == 200 and "native" not in result.data


def test_native_config_present_when_any_live_makerspace_enables_mobile():
    disabled = make_space("native-config-disabled")
    disable_module(disabled, "mobile")
    make_space("native-config-enabled")
    result = APIClient().get(CONFIG)
    assert result.status_code == 200
    assert result.data["native"]["min_app_version"] == {"android": None, "ios": None}


def test_native_config_advertises_existing_native_credentials_and_minimum_versions(sms_on):
    make_space("native-config-providers")
    registration("android", min_supported_version="2.10.3")
    registration("apple", min_supported_version="1.4.0")
    row = PlatformSocialAuthSettings.load()
    row.google_android_client_id = "android-client.apps.googleusercontent.com"
    row.google_ios_client_id = "ios-client.apps.googleusercontent.com"
    row.apple_native_app_ids = [APP_ID]
    # Web credentials deliberately absent: native discovery must use the native fields.
    row.google_web_client_id = ""
    row.apple_service_id = ""
    row.save()
    oidc = make_provider(
        slug="native-campus", display_name="Campus", issuer="https://id.example.test",
        jwks_url="https://id.example.test/jwks", client_id="public-campus-client",
    )
    make_provider(slug="native-disabled", display_name="Disabled", is_enabled=False)

    result = APIClient().get(CONFIG)

    assert result.status_code == 200
    assert result.data["native"] == {
        "app_display_name": "SpaceWorks",
        "app_identity": {"android": {"app_id": APP, "signing_identities": [FIRST, SECOND]},
                         "ios": {"app_id": APP, "signing_identities": [PREFIX]}},
        "min_app_version": {"android": "2.10.3", "ios": "1.4.0"},
        "providers": {
            "password": True, "phone": True,
            "google": {"android_client_id": row.google_android_client_id,
                       "ios_client_id": row.google_ios_client_id},
            "apple": {"enabled": True},
            "oidc": [{"key": oidc.provider_key, "display_name": oidc.display_name,
                      "client_id": oidc.client_id, "issuer": oidc.issuer}],
        },
    }


@pytest.mark.parametrize("switch", [
    "password_enabled", "phone_enabled", "social_enabled", "google_enabled", "apple_enabled",
])
def test_native_provider_discovery_respects_existing_login_switches(settings, sms_on, switch):
    configure_native_social(settings)
    row = PlatformSocialAuthSettings.load()
    row.apple_native_app_ids = [APP_ID]
    row.save(update_fields=["apple_native_app_ids", "updated_at"])
    oidc = make_provider()
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={switch: False})
    providers = APIClient().get(CONFIG).data["native"]["providers"]
    assert providers["password"] is (switch != "password_enabled")
    assert providers["phone"] is (switch != "phone_enabled")
    assert (providers["google"] is not None) is (switch not in {"google_enabled", "social_enabled"})
    assert (providers["apple"] is not None) is (switch not in {"apple_enabled", "social_enabled"})
    assert providers["oidc"] == ([] if switch == "social_enabled" else [{
        "key": oidc.provider_key, "display_name": oidc.display_name,
        "client_id": oidc.client_id, "issuer": oidc.issuer,
    }])


def test_native_config_does_not_advertise_unconfigured_methods():
    make_space("native-config-unconfigured")
    providers = APIClient().get(CONFIG).data["native"]["providers"]
    assert providers == {"password": True, "phone": False, "google": None, "apple": None, "oidc": []}


def apple_nonce(challenge):
    return APIClient().post(NONCE_URL, {
        "provider": "apple", "surface": "member", "delivery": "device",
        "client_platform": "ios", "challenge": challenge,
    }, format="json")


def apple_login(nonce, challenge):
    return APIClient().post("/api/v1/auth/social/apple", {
        "id_token": "apple-native-id-token", "nonce": nonce, "surface": "member",
        "delivery": "device", "client_platform": "ios", "challenge": challenge,
        "attestation": {"assertion": "opaque"},
    }, format="json")


def test_native_apple_first_signin_passes_attested_app_id_as_single_audience(settings, monkeypatch):
    configure_native_social(settings)
    row = PlatformSocialAuthSettings.load()
    row.apple_native_app_ids = ["org.spaceworks.other", APP_ID]
    row.apple_service_id = ""
    row.save()
    user = make_user("apple-native-first", email_verified_at=timezone.now())
    challenge = issue_challenge(APIClient())
    nonce = apple_nonce(challenge)
    assert nonce.status_code == 200
    mock_identity(monkeypatch, user)
    # The same token-verification seam used by the existing social tests, with the
    # audience argument checked explicitly to catch the former list/string mismatch.
    from apps.accounts.views_social import _verify
    verifier = Mock(wraps=_verify)
    monkeypatch.setattr("apps.accounts.views_social._verify", verifier)
    mock_attestation(monkeypatch, challenge)

    result = apple_login(nonce.data["nonce"], challenge)

    assert result.status_code == 200
    verifier.assert_called_once_with("apple", "apple-native-id-token", nonce.data["nonce"], APP_ID)
    assert DeviceGrant.objects.get(user=user).registration.app_id == APP_ID
    assert AccessToken(result.data["access"])["surface"] == "member"
    assert result.data["user"]["session_authority"] == "member"
    assert not result.cookies


@pytest.mark.parametrize("remove_after_nonce", [False, True])
def test_native_apple_rejects_app_ids_outside_the_native_allowlist(
    settings, monkeypatch, remove_after_nonce,
):
    configure_native_social(settings)
    row = PlatformSocialAuthSettings.load()
    row.apple_native_app_ids = [APP_ID] if remove_after_nonce else ["org.spaceworks.other"]
    row.save()
    challenge = issue_challenge(APIClient())
    verifier = Mock()
    monkeypatch.setattr("apps.accounts.views_social._verify", verifier)
    nonce = apple_nonce(challenge)
    if remove_after_nonce:
        assert nonce.status_code == 200
        row.apple_native_app_ids = ["org.spaceworks.other"]
        row.save(update_fields=["apple_native_app_ids", "updated_at"])
        result = apple_login(nonce.data["nonce"], challenge)
        assert result.status_code == 409
        assert result.data["code"] == "social_device_restart_required"
    else:
        assert nonce.status_code == 403
    verifier.assert_not_called()
    assert not DeviceGrant.objects.exists()
