"""Native-only providers and OIDC use fresh, nonce-bound existing identities."""

from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import account_restore_social as service
from apps.accounts.account_restore import restore_disclosure
from apps.accounts.models import SocialIdentity
from apps.accounts.models_account_restore import AccountRestoreIntent
from apps.accounts.models_social import PlatformSocialAuthSettings
from tests.accounts.restore_helpers_m1d import archive, restore_config
from tests.accounts.test_account_restore_social_m1d import req
from tests.accounts.test_support_m1d import account, m1d_config
from tests.accounts.test_social_first_grant import issue_challenge, APP_ID
from tests.accounts.native_helpers_m1d import configure_native_social, mock_attestation
from tests.accounts.test_reauthentication import ORIGIN

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("provider", ["apple", "google"])
@pytest.mark.parametrize("failure", [None, "foreign_challenge", "missing_auth_time", "missing_attestation"])
def test_native_only_linked_provider_restore_requires_exact_app_and_fresh_token(provider, failure, settings, monkeypatch):
    configure_native_social(settings)
    configuration = PlatformSocialAuthSettings.load()
    configuration.apple_native_app_ids = [APP_ID]
    configuration.save()
    user = account()
    user.email = ""
    user.save()
    SocialIdentity.objects.create(user=user, provider=provider, provider_sub="native-linked")
    assert restore_disclosure(user)["restorable"]
    archive(user)
    raw = issue_challenge(APIClient())
    started = APIClient().post("/api/v1/auth/account/restore/social/start", {
        "username": user.username, "provider": provider, "delivery": "device",
        "client_platform": "ios", "challenge": raw,
    }, format="json")
    assert started.status_code == 200
    mock_attestation(monkeypatch, raw)
    parser = Mock(return_value={"sub": "native-linked", "auth_time": None if failure == "missing_auth_time"
                               else timezone.now().timestamp()})
    monkeypatch.setattr(f"apps.accounts.social_{provider}.verify_{provider}_token", parser)
    supplied = issue_challenge(APIClient()) if failure == "foreign_challenge" else raw
    data = {"state": started.data["state"], "nonce": started.data["nonce"], "id_token": "signed-native",
            "challenge": supplied, "attestation": {"assertion": "opaque"}}
    if failure == "missing_attestation":
        data.pop("attestation")
    result = APIClient().post("/api/v1/auth/account/restore/social/complete", data, format="json")
    assert result.status_code == (401 if failure else 200)
    assert AccountRestoreIntent.objects.get(user=user).consumed_at
    user.refresh_from_db()
    assert user.is_active is (failure is None)
    assert not result.cookies and "access" not in result.data
    if not failure:
        parser.assert_called_once_with("signed-native", nonce=started.data["nonce"], audience=(
            APP_ID if provider == "apple" else configuration.google_ios_client_id))


@pytest.mark.parametrize("kind", ["disabled", "unconfigured", "unverified_phone"])
def test_preflight_does_not_advertise_an_unusable_recovery_channel(kind):
    from apps.accounts.models import PlatformLoginMethods
    user = account(password=None)
    user.email = ""
    user.save()
    SocialIdentity.objects.create(user=user, provider="google", provider_sub="linked")
    configuration = PlatformSocialAuthSettings.load()
    configuration.google_web_client_id = "web-client" if kind != "unconfigured" else ""
    configuration.save()
    if kind == "disabled":
        switches = PlatformLoginMethods.load()
        switches.google_enabled = False
        switches.save()
    elif kind == "unverified_phone":
        user.phone_e164 = "+14155552671"
        user.save()
    assert restore_disclosure(user)["restorable"] is False


@pytest.mark.parametrize("auth_time", ["fresh", "missing", "stale"])
def test_oidc_restore_verifies_exchanged_token_nonce_subject_and_auth_time(auth_time, monkeypatch):
    from apps.accounts.models_oidc import OidcProvider
    from apps.accounts import reauthentication_intents as intents
    from rest_framework.exceptions import AuthenticationFailed
    provider = OidcProvider.objects.create(slug="restore-idp", display_name="Restore IdP",
        issuer="https://idp.example", jwks_url="https://idp.example/jwks", client_id="oidc-client")
    user = account()
    user.email = ""
    user.save()
    SocialIdentity.objects.create(user=user, provider=provider.provider_key, provider_sub="oidc-linked")
    archive(user)
    monkeypatch.setattr(intents, "discover", lambda row: {"authorization_endpoint": "https://idp.example/auth"})
    exchange = Mock(return_value="exchanged-id-token")
    monkeypatch.setattr(intents, "exchange_code", exchange)
    proof = service.start_social(req(), username=user.username, provider=provider.provider_key,
                                 redirect_uri=ORIGIN + "/restore-callback")
    value = None if auth_time == "missing" else timezone.now().timestamp() - (600 if auth_time == "stale" else 0)
    monkeypatch.setattr("apps.accounts.social_oidc.decode_rs256_token", lambda *a, **kw: {
        "sub": "oidc-linked", "nonce": proof["nonce"], "auth_time": value})
    def complete():
        return service.complete_social(req(), state=proof["state"], nonce=proof["nonce"], code="fresh-code")
    if auth_time == "fresh":
        complete()
    else:
        with pytest.raises(AuthenticationFailed):
            complete()
    assert exchange.call_args.kwargs["code"] == "fresh-code"
    assert exchange.call_args.kwargs["redirect_uri"] == ORIGIN + "/restore-callback"
    assert exchange.call_args.kwargs["code_verifier"]
    user.refresh_from_db()
    assert user.is_active is (auth_time == "fresh")
