"""Native passkeys (decision 358 B), driven by the software authenticator and real ceremonies.

The RP ID is always the deployment's public web domain and the expected origin comes from the
attested app (iOS `https://<rp id>`, Android `android:apk-key-hash:...`), never from a header.
Registration from the phone needs recent re-authentication exactly as on the web.
"""
import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import DeviceGrant, User
from apps.accounts.models_login_methods import PlatformLoginMethods
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.passkeys.ceremonies import b64url
from apps.accounts.passkeys.native import android_origin, app_origin, expected_origins
from apps.accounts.reauthentication import versions
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.audit.models import AuditLog
from tests.accounts.account_factories import device_grant
from tests.accounts.passkey_helpers import SoftAuthenticator
from tests.accounts.test_native_github_0120 import attestation_echo
from tests.accounts.test_social_first_grant import APP_ID, configure_native_social, issue_challenge
from tests.device_helpers import make_native_app_registration

pytestmark = pytest.mark.django_db
BASE = "https://spaces.example.test"
RP_ID = "spaces.example.test"
OPTIONS = "/api/v1/auth/device/passkey/options"
LOGIN = "/api/v1/auth/device/passkey/login"
PASSWORD = "Native passkey password 58!"


@pytest.fixture(autouse=True)
def deployment(settings, monkeypatch):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.PUBLIC_APP_BASE_URL = BASE
    settings.PLATFORM_STAFF_ORIGINS = [BASE]
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    cache.clear()
    configure_native_social(settings)
    monkeypatch.setattr("apps.accounts.attestation_apple.requests.post", attestation_echo)


def phone(user, *, recent=True, platform="apple", **grant_fields):
    grant = device_grant(user, platform=platform, **grant_fields)
    access, _refresh, family = issue_device_token_pair(user, grant)
    if recent:
        ReauthenticationSession.objects.update_or_create(session_id=f"device:{family.pk}", defaults={
            "user": user, "surface": "member", "auth_time": timezone.now(), **versions(user)})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client, grant


def stored(user, authenticator):
    """A passkey already registered on the deployment's RP ID."""
    return WebAuthnCredential.objects.create(
        user=user, credential_id=b64url(authenticator.credential_id), public_key=authenticator._cose(),
        sign_count=0, transports=["internal"], rp_id=RP_ID, name="Phone")


def native_sign_in(authenticator, *, origin=None):
    challenge = issue_challenge(APIClient())
    identity = {"platform": "apple", "app_id": APP_ID, "environment": "development"}
    options = APIClient().post(OPTIONS, {**identity, "challenge": challenge}, format="json")
    assert options.status_code == 200, options.data
    assert options.data["options"]["rpId"] == RP_ID
    credential = authenticator.assertion(options.data["options"], origin=origin)
    body = {**identity, "challenge": challenge, "attestation": {"assertion": "opaque"},
            "ceremony": options.data["ceremony"], "credential": credential}
    return APIClient().post(LOGIN, body, format="json"), body


def test_registration_from_the_phone_keeps_the_grant_and_uses_the_fixed_rp_id():
    person = User.objects.create_user("native-passkey-add", password=PASSWORD)
    client, grant = phone(person)
    # A client-controlled Origin header never chooses the RP ID on a native session.
    options = client.post("/api/v1/auth/passkeys/register/options", HTTP_ORIGIN="https://evil.example.test")
    assert options.status_code == 200, options.data
    assert options.data["options"]["rp"]["id"] == RP_ID
    authenticator = SoftAuthenticator(origin=BASE, rp_id=RP_ID)
    done = client.post("/api/v1/auth/passkeys/register/verify", {
        "ceremony": options.data["ceremony"], "credential": authenticator.register(options.data["options"]),
        "name": "Phone"}, format="json")
    assert done.status_code == 200, done.data
    assert done.data["refresh"] and done.data["device_grant"]["id"] == str(grant.pk)
    assert "refresh_token" not in done.cookies
    assert WebAuthnCredential.objects.get(user=person).rp_id == RP_ID
    assert DeviceGrant.objects.get(pk=grant.pk).status == DeviceGrant.Status.ACTIVE
    claims = AccessToken(done.data["access"])
    assert claims["mfa_source"] == "verified" and claims["mfa_method"] == "passkey"
    renewed = APIClient()
    renewed.credentials(HTTP_AUTHORIZATION=f"Bearer {done.data['access']}")
    assert renewed.get("/api/v1/auth/me").status_code == 200
    assert AuditLog.objects.filter(action="auth.passkey_registered", actor=person).exists()


def test_registration_from_the_phone_needs_recent_reauthentication():
    person = User.objects.create_user("native-passkey-stale", password=PASSWORD)
    client, _grant = phone(person, recent=False)
    refused = client.post("/api/v1/auth/passkeys/register/options")
    assert refused.status_code == 403 and refused.data["code"] == "recent_reauth_required"


def test_android_origin_is_the_signing_certificate_hash():
    digest = "ab" * 32
    assert android_origin(digest) == "android:apk-key-hash:" + b64url(bytes.fromhex(digest))
    apple = type("Grant", (), {"platform": "apple", "signing_identity": "TEAMID1234"})()
    assert app_origin(apple, RP_ID) == f"https://{RP_ID}"


def android_app(*digests):
    registration = make_native_app_registration(app_id="org.spaceworks.android", platform="android")
    registration.signing_identities = list(digests)
    registration.save(update_fields=["signing_identities", "updated_at"])
    return registration


def test_android_passkeys_accept_every_active_signer_of_the_registration():
    """Decision 361 item 3: the grant pinned the FIRST signer; the app now ships signed with the
    SECOND (key rotation) and its passkey ceremony still verifies. An unknown signer never does."""
    first, second, stranger = "ab" * 32, "cd" * 32, "ef" * 32
    registration = android_app(first, second)
    assert expected_origins(f"android-registration:{registration.pk}") == [
        android_origin(first), android_origin(second)]
    person = User.objects.create_user("native-passkey-rotated", password=PASSWORD)
    client, _grant = phone(person, platform="android", registration=registration, signing_identity=first)
    options = client.post("/api/v1/auth/passkeys/register/options")
    assert options.status_code == 200, options.data
    rotated = SoftAuthenticator(origin=android_origin(second), rp_id=RP_ID)
    done = client.post("/api/v1/auth/passkeys/register/verify", {
        "ceremony": options.data["ceremony"], "credential": rotated.register(options.data["options"])},
        format="json")
    assert done.status_code == 200, done.data
    other = User.objects.create_user("native-passkey-stranger", password=PASSWORD)
    other_client, _grant = phone(other, platform="android", registration=registration, signing_identity=first)
    options = other_client.post("/api/v1/auth/passkeys/register/options")
    forged = SoftAuthenticator(origin=android_origin(stranger), rp_id=RP_ID)
    refused = other_client.post("/api/v1/auth/passkeys/register/verify", {
        "ceremony": options.data["ceremony"], "credential": forged.register(options.data["options"])},
        format="json")
    assert refused.status_code == 400 and refused.data["code"] == "passkey_failed"


def _password_sign_in(person):
    challenge = issue_challenge(APIClient())
    return APIClient().post("/api/v1/auth/device/login", {
        "username": person.username, "password": PASSWORD, "platform": "apple", "app_id": APP_ID,
        "environment": "development", "challenge": challenge, "attestation": {"assertion": "opaque"}},
        format="json")


def _second_factor(first, authenticator):
    options = APIClient().post("/api/v1/auth/mfa/passkey/options", {"challenge": first.data["challenge"]},
                               format="json")
    assert options.status_code == 200, options.data
    assert options.data["options"]["rpId"] == RP_ID
    return APIClient().post("/api/v1/auth/mfa/verify", {
        "challenge": first.data["challenge"], "factor": "passkey",
        "webauthn": {"ceremony": options.data["ceremony"],
                     "credential": authenticator.assertion(options.data["options"])},
    }, format="json")


def test_passkey_is_the_second_factor_of_a_native_password_sign_in():
    """Decision 361 item 4: a device MFA challenge offers `passkey`, scoped to the attested app."""
    person = User.objects.create_user("native-passkey-factor", password=PASSWORD)
    authenticator = SoftAuthenticator(origin=BASE, rp_id=RP_ID)
    stored(person, authenticator)
    first = _password_sign_in(person)
    assert first.status_code == 200 and first.data["mfa_required"] is True, first.data
    assert "passkey" in first.data["factors"]
    done = _second_factor(first, authenticator)
    assert done.status_code == 200, done.data
    assert done.data["device_grant"] and done.data["refresh"]
    claims = AccessToken(done.data["access"])
    assert claims["mfa_source"] == "verified" and claims["mfa_method"] == "passkey"
    assert DeviceGrant.objects.get(user=person).login_method == "password"


def test_native_second_factor_refuses_an_assertion_for_another_origin():
    person = User.objects.create_user("native-passkey-factor-origin", password=PASSWORD)
    authenticator = SoftAuthenticator(origin="https://evil.example.test", rp_id=RP_ID)
    stored(person, authenticator)
    first = _password_sign_in(person)
    assert first.status_code == 200 and first.data["mfa_required"] is True, first.data
    refused = _second_factor(first, authenticator)
    assert refused.status_code == 400 and refused.data["code"] == "passkey_failed"
    assert not DeviceGrant.objects.filter(user=person).exists()


def test_association_files_are_served_on_the_platform_domain_suffix_host(settings):
    """Decision 361 item 5: under managed hosting the passkey RP ID is the suffix, so iOS
    `webcredentials` must be published on the suffix host itself."""
    from apps.accounts.mobile_associations import association_components, association_host_kind
    from apps.accounts.passkeys.native import native_rp_id
    from apps.makerspaces import hosting
    from tests.accounts.mobile_integration_helpers import APP, PREFIX, registration
    settings.ALLOWED_HOSTS = ["*"]
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    settings.PLATFORM_STAFF_ORIGINS = ["https://app.example.test"]
    settings.PLATFORM_DOMAIN_SUFFIX = ".example.test"
    settings.INFRA_HOSTS = {"app.example.test", "example.test"}
    settings.ENABLE_HTTPS = False
    settings.SECURE_SSL_REDIRECT = False
    hosting.invalidate()
    registration("apple")
    assert native_rp_id() == "example.test"
    assert association_host_kind("example.test") == "suffix"
    assert {"/": "/app/auth/github/callback"} not in association_components("suffix")
    served = APIClient().get("/.well-known/apple-app-site-association", HTTP_HOST="example.test")
    assert served.status_code == 200, served.content
    assert served.json()["webcredentials"]["apps"] == [f"{PREFIX}.{APP}"]


def test_native_sign_in_issues_an_attested_member_grant_verified_by_the_passkey():
    person = User.objects.create_user("native-passkey-login", password=PASSWORD)
    authenticator = SoftAuthenticator(origin=BASE, rp_id=RP_ID)
    stored(person, authenticator)
    response, body = native_sign_in(authenticator)
    assert response.status_code == 200, response.data
    grant = DeviceGrant.objects.get(user=person)
    assert grant.authority == "member" and grant.login_method == "passkey"
    claims = AccessToken(response.data["access"])
    assert claims["mfa_source"] == "verified" and claims["mfa_method"] == "passkey"
    assert claims["device_grant_id"] == str(grant.pk) and response.data["refresh"]
    assert AuditLog.objects.filter(action="auth.passkey_login_succeeded", actor=person).exists()
    replay = APIClient().post(LOGIN, body, format="json")  # challenge and ceremony are both spent
    assert replay.status_code == 401
    assert DeviceGrant.objects.filter(user=person).count() == 1


def test_native_sign_in_refuses_an_assertion_made_for_another_origin():
    person = User.objects.create_user("native-passkey-origin", password=PASSWORD)
    authenticator = SoftAuthenticator(origin=BASE, rp_id=RP_ID)
    stored(person, authenticator)
    response, _body = native_sign_in(authenticator, origin="https://evil.example.test")
    assert response.status_code == 400 and response.data["code"] == "passkey_failed"
    assert not DeviceGrant.objects.filter(user=person).exists()
    assert AuditLog.objects.filter(action="auth.passkey_login_failed").exists()


def test_native_passkeys_follow_the_platform_switch():
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"passkeys_enabled": False})
    cache.clear()
    challenge = issue_challenge(APIClient())
    refused = APIClient().post(OPTIONS, {"platform": "apple", "app_id": APP_ID, "environment": "development",
                                         "challenge": challenge}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "passkeys_unavailable"


def test_native_sign_in_needs_a_live_attestation_challenge():
    refused = APIClient().post(OPTIONS, {"platform": "apple", "app_id": APP_ID, "environment": "development",
                                         "challenge": "never-issued"}, format="json")
    assert refused.status_code == 401
