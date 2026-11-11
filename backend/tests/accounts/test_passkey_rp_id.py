"""S-A: passkey ceremonies end to end (software authenticator) and the relying-party ID."""

import pytest
from cryptography.fernet import Fernet
from django.core.checks import Error, Warning
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.passkeys import rp_id as rp
from apps.accounts.passkeys.checks import passkey_rp_ids
from apps.accounts.reauthentication import versions
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff
from tests.accounts.passkey_helpers import SoftAuthenticator

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"
PASSWORD = "Passkey ceremony password 55!"


@pytest.fixture(autouse=True)
def origins(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.PUBLIC_APP_BASE_URL = ORIGIN
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PLATFORM_DOMAIN_SUFFIX = ""


def session(user, *, recent=True):
    from apps.accounts.mfa_policy import is_enrolled, stamp
    if is_enrolled(user):  # an enrolled person's session carries its proof, as after a real sign-in
        stamp(user, UserMFA.objects.get_or_create(user=user)[0], "passkey")
    token = SpaceWorksRefreshToken.for_user(user).access_token
    if recent:
        ReauthenticationSession.objects.update_or_create(session_id=token["sid"], defaults={
            "user": user, "surface": token["surface"], "auth_time": timezone.now(), **versions(user)})
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN=ORIGIN)
    return api


def register(user, authenticator=None):
    authenticator = authenticator or SoftAuthenticator()
    api = session(user)
    options = api.post("/api/v1/auth/passkeys/register/options")
    assert options.status_code == 200, options.data
    assert options.data["options"]["rp"]["id"] == "localhost"
    done = api.post("/api/v1/auth/passkeys/register/verify", {
        "ceremony": options.data["ceremony"], "credential": authenticator.register(options.data["options"]),
        "name": "Laptop"}, format="json")
    assert done.status_code == 200, done.data
    return authenticator, done


def sign_in(authenticator, **kwargs):
    api = APIClient()
    options = api.post("/api/v1/auth/passkeys/authenticate/options", HTTP_ORIGIN=ORIGIN)
    assert options.status_code == 200, options.data
    return api.post("/api/v1/auth/passkeys/authenticate/verify", {
        "ceremony": options.data["ceremony"], "credential": authenticator.assertion(options.data["options"], **kwargs)},
        format="json", HTTP_ORIGIN=ORIGIN)


def test_register_then_sign_in_is_verified_with_the_passkey_method():
    person = User.objects.create_user("passkey-person", password=PASSWORD)
    authenticator, done = register(person)
    assert done.data["recovery_codes"] and len(done.data["recovery_codes"]) == 10
    assert done.data["passkey"]["name"] == "Laptop" and done.data["passkey"]["rp_id"] == "localhost"
    assert WebAuthnCredential.objects.filter(user=person).count() == 1
    assert AuditLog.objects.filter(action="auth.passkey_registered").exists()
    response = sign_in(authenticator)
    assert response.status_code == 200, response.data
    from rest_framework_simplejwt.tokens import AccessToken
    claims = AccessToken(response.data["access"])
    assert claims["mfa_source"] == "verified" and claims["mfa_method"] == "passkey"
    assert claims["mfa_version"] == str(UserMFA.objects.get(user=person).version)
    assert AuditLog.objects.filter(action="auth.passkey_login_succeeded").exists()


def test_registration_needs_recent_reauthentication():
    person = User.objects.create_user("passkey-stale", password=PASSWORD)
    refused = session(person, recent=False).post("/api/v1/auth/passkeys/register/options")
    assert refused.status_code == 403 and refused.data["code"] == "recent_reauth_required"


def test_staff_passkey_satisfies_staff_routes():
    space = Makerspace.objects.create(name="Passkey staff", slug="passkey-staff")
    staff = make_staff(space, username="passkey-staff", password=PASSWORD)
    authenticator, _ = register(staff)
    response = sign_in(authenticator)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}", HTTP_ORIGIN=ORIGIN)
    assert api.get(f"/api/v1/admin/makerspaces/{space.pk}/security-settings").status_code == 200


def test_sign_count_regression_and_replay_are_refused():
    person = User.objects.create_user("passkey-clone", password=PASSWORD)
    authenticator, _ = register(person)
    assert sign_in(authenticator, count=5).status_code == 200
    cloned = sign_in(authenticator, count=3)
    assert cloned.status_code == 400 and cloned.data["code"] == "passkey_failed"
    assert AuditLog.objects.filter(action="auth.passkey_login_failed").exists()
    api = APIClient()
    options = api.post("/api/v1/auth/passkeys/authenticate/options", HTTP_ORIGIN=ORIGIN).data
    answer = authenticator.assertion(options["options"], count=10)
    body = {"ceremony": options["ceremony"], "credential": answer}
    assert api.post("/api/v1/auth/passkeys/authenticate/verify", body, format="json",
                    HTTP_ORIGIN=ORIGIN).status_code == 200
    assert api.post("/api/v1/auth/passkeys/authenticate/verify", body, format="json",
                    HTTP_ORIGIN=ORIGIN).status_code == 400  # the ceremony is spent


def test_forged_origin_is_refused():
    person = User.objects.create_user("passkey-forged", password=PASSWORD)
    authenticator, _ = register(person)
    assert APIClient().post("/api/v1/auth/passkeys/authenticate/options",
                            HTTP_ORIGIN="https://evil.example.com").data["code"] == "rp_id_unavailable"
    api = APIClient()
    options = api.post("/api/v1/auth/passkeys/authenticate/options", HTTP_ORIGIN=ORIGIN).data
    forged = authenticator.assertion(options["options"], origin="https://evil.example.com")
    assert api.post("/api/v1/auth/passkeys/authenticate/verify", {"ceremony": options["ceremony"],
                    "credential": forged}, format="json", HTTP_ORIGIN=ORIGIN).status_code == 400


def test_user_verification_is_required_for_sign_in():
    person = User.objects.create_user("passkey-uv", password=PASSWORD)
    authenticator, _ = register(person)
    assert sign_in(authenticator, uv=False).status_code == 400


def test_rp_id_rules(settings):
    assert rp.rp_id_for_origin(ORIGIN) == "localhost"
    with pytest.raises(rp.RpIdUnavailable):
        rp.rp_id_for_origin("https://unknown.example.org")
    space = Makerspace.objects.create(name="Custom", slug="custom", frontend_domain="lab.example.org",
                                      frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    assert rp.rp_id_for_origin("https://lab.example.org") == "lab.example.org"
    assert space.pk
    with pytest.raises(rp.RpIdUnavailable):
        rp.rp_id_for_origin("http://lab.example.org")  # a custom domain is https only
    settings.PLATFORM_DOMAIN_SUFFIX = ".spaceworks.example"
    Makerspace.objects.create(name="Sub", slug="sub", frontend_domain="sub.spaceworks.example",
                              frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    assert rp.rp_id_for_origin("https://sub.spaceworks.example") == "spaceworks.example"
    for host in ("github.io", "co.uk", "com", "127.0.0.1"):
        with pytest.raises(rp.RpIdUnavailable):
            rp.validate_rp_id(host)


def test_system_check_refuses_a_public_suffix(settings):
    settings.PUBLIC_APP_BASE_URL = "https://github.io"
    settings.PLATFORM_STAFF_ORIGINS = ["http://192.168.1.10:5000"]
    problems = passkey_rp_ids()
    assert any(isinstance(item, Error) and item.id == "accounts.E010" for item in problems)
    assert any(isinstance(item, Warning) and item.id == "accounts.W010" for item in problems)


def test_orphaned_rp_id_still_counts_but_is_not_offered():
    from apps.accounts.mfa_policy import is_enrolled
    person = User.objects.create_user("passkey-orphan", password=PASSWORD)
    WebAuthnCredential.objects.create(user=person, credential_id="orphan", public_key=b"k", rp_id="old.example.org")
    assert is_enrolled(person)
    listing = session(person).get("/api/v1/auth/passkeys")
    assert listing.status_code == 200 and listing.data["passkeys"][0]["usable_here"] is False


def test_staff_cannot_remove_their_last_factor_but_members_can():
    space = Makerspace.objects.create(name="Last", slug="last")
    staff = make_staff(space, username="passkey-last", password=PASSWORD)
    register(staff)
    row = WebAuthnCredential.objects.get(user=staff)
    refused = session(staff).delete(f"/api/v1/auth/passkeys/{row.pk}")
    assert refused.status_code == 403 and refused.data["code"] == "last_factor"
    member = User.objects.create_user("passkey-member-remove", password=PASSWORD)
    register(member)
    mine = WebAuthnCredential.objects.get(user=member)
    removed = session(member).delete(f"/api/v1/auth/passkeys/{mine.pk}")
    assert removed.status_code == 200 and not WebAuthnCredential.objects.filter(user=member).exists()
    assert AuditLog.objects.filter(action="auth.passkey_removed").exists()


def test_passkeys_switched_off_by_the_platform():
    from django.core.cache import cache
    from apps.accounts.models import PlatformLoginMethods
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"passkeys_enabled": False})
    cache.clear()
    assert APIClient().get("/api/v1/config").data["passkeys_enabled"] is False
    refused = APIClient().post("/api/v1/auth/passkeys/authenticate/options", HTTP_ORIGIN=ORIGIN)
    assert refused.status_code == 403 and refused.data["code"] == "passkeys_unavailable"


def test_passkey_reauthentication_stamps_the_window():
    person = User.objects.create_user("passkey-reauth", password=PASSWORD)
    authenticator, done = register(person)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {done.data['access']}", HTTP_ORIGIN=ORIGIN)
    options = api.post("/api/v1/auth/reauth/passkey/options")
    assert options.status_code == 200, options.data
    verified = api.post("/api/v1/auth/reauth/passkey", {"ceremony": options.data["ceremony"],
                        "credential": authenticator.assertion(options.data["options"])}, format="json")
    assert verified.status_code == 200 and verified.data["verified"] is True
    refused = api.post("/api/v1/auth/reauth", {"password": PASSWORD}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "passkey_required"


def test_second_factor_options_and_verify_helper():
    from apps.accounts.mfa_challenges import digest
    from apps.accounts.models_mfa import MFAChallenge
    from apps.accounts.passkeys.assertion import verify_mfa
    person = User.objects.create_user("passkey-second", password=PASSWORD)
    authenticator, _ = register(person)
    login = APIClient().post("/api/v1/auth/login", {"username": person.username, "password": PASSWORD},
                             format="json", HTTP_ORIGIN=ORIGIN)
    assert login.status_code == 200 and login.data.get("mfa_required") is True, login.data
    options = APIClient().post("/api/v1/auth/mfa/passkey/options", {"challenge": login.data["challenge"]},
                               format="json", HTTP_ORIGIN=ORIGIN)
    assert options.status_code == 200, options.data
    challenge = MFAChallenge.objects.get(token_digest=digest(login.data["challenge"]))

    class Request:
        headers = {"Origin": ORIGIN}

    row = verify_mfa(challenge, options.data["ceremony"], authenticator.assertion(options.data["options"]), Request())
    assert row.user_id == person.pk and row.last_used_at is not None
