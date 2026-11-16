"""Native account settings: authenticator enrollment and provider linking on a device session."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.mfa_crypto import totp
from apps.accounts.models import DeviceGrant
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.models_social import SocialIdentity
from apps.audit.models import AuditLog
from tests.accounts.account_factories import make_staff
from tests.accounts.native_helpers_m1d import attested_staff_login
from tests.accounts.test_device_auth import attested_login
from tests.accounts.test_password_login_surfaces_p3ii import _bearer
from tests.accounts.test_social_auth import NONCE_URL, configure_google, mock_claims, nonce
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"
LINK = "/api/v1/auth/social/providers"


def member_device(settings, monkeypatch, username):
    space = make_space(f"{username}-space")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"mobile"})
    space.save(update_fields=["enabled_modules"])
    user = make_user(username, password=PASSWORD, access_status="active", email_verified_at=timezone.now())
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200, login.data
    return user, login.data


def start_enrollment(client):
    response = client.post("/api/v1/auth/mfa", {"password": PASSWORD}, format="json")
    assert response.status_code == 200, response.data
    return response.data["challenge"]


def current_code(secret):
    return totp(secret, int(timezone.now().timestamp() // 30))


def test_member_enrolls_authenticator_on_the_same_device_grant(settings, monkeypatch):
    user, first = member_device(settings, monkeypatch, "native-enroll")
    second, _ = attested_login(APIClient(), user, settings, monkeypatch)
    raw = start_enrollment(_bearer(first["access"]))
    # Starting invalidates the current tokens, so the challenge alone is the credential.
    client = APIClient()
    setup = client.post("/api/v1/auth/mfa/enroll", {"challenge": raw}, format="json")
    assert setup.status_code == 200, setup.data
    done = client.post("/api/v1/auth/mfa/confirm",
                       {"challenge": raw, "code": current_code(setup.data["secret"])}, format="json")

    assert done.status_code == 200, done.data
    assert done.data["device_grant"]["id"] == first["device_grant"]["id"]
    assert done.data["recovery_codes"] and done.data["refresh"]
    assert settings.AUTH_REFRESH_COOKIE not in done.cookies
    assert UserMFA.objects.get(user=user).enabled_at is not None
    kept = DeviceGrant.objects.get(pk=first["device_grant"]["id"])
    other = DeviceGrant.objects.get(pk=second.data["device_grant"]["id"])
    assert kept.status == DeviceGrant.Status.ACTIVE and other.status == DeviceGrant.Status.REVOKED
    assert _bearer(first["access"]).get("/api/v1/auth/me").status_code == 401
    assert _bearer(done.data["access"]).get("/api/v1/auth/me").status_code == 200
    stale = APIClient().post("/api/v1/auth/device/refresh", {"refresh": first["refresh"]}, format="json")
    assert stale.status_code == 401
    audit = AuditLog.objects.filter(action="auth.mfa_enabled", target_id=str(user.pk)).latest("pk")
    assert audit.meta["delivery"] == "device" and audit.meta["grant_hash"]


def test_settings_challenge_finishes_only_on_the_grant_that_started_it(settings, monkeypatch):
    user, first = member_device(settings, monkeypatch, "native-enroll-bound")
    raw = start_enrollment(_bearer(first["access"]))
    setup = APIClient().post("/api/v1/auth/mfa/enroll", {"challenge": raw}, format="json")
    assert setup.status_code == 200, setup.data
    code = current_code(setup.data["secret"])

    browser = APIClient().post("/api/v1/auth/mfa/confirm", {"challenge": raw, "code": code},
                               format="json", HTTP_ORIGIN="http://localhost:5173")
    assert browser.status_code in (401, 403)
    assert UserMFA.objects.get(user=user).enabled_at is None

    DeviceGrant.objects.filter(pk=first["device_grant"]["id"]).update(status=DeviceGrant.Status.REVOKED)
    revoked = APIClient().post("/api/v1/auth/mfa/confirm", {"challenge": raw, "code": code}, format="json")
    assert revoked.status_code == 401
    assert UserMFA.objects.get(user=user).enabled_at is None


def test_device_enrollment_refuses_wrong_password(settings, monkeypatch):
    _user, first = member_device(settings, monkeypatch, "native-enroll-password")
    response = _bearer(first["access"]).post("/api/v1/auth/mfa", {"password": "wrong"}, format="json")
    assert response.status_code == 401


def test_native_staff_settings_enrollment_is_refused(settings, monkeypatch):
    space = make_space("native-staff-enroll")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"mobile"})
    space.save(update_fields=["enabled_modules"])
    staff = make_staff(space, username="native-staff-enroll", role_slug="inventory_manager", password=PASSWORD)
    login, _ = attested_staff_login(APIClient(), staff, settings, monkeypatch)
    assert login.status_code == 200
    before = MFAChallenge.objects.filter(user=staff).count()
    response = _bearer(login.data["access"]).post("/api/v1/auth/mfa", {"password": PASSWORD}, format="json")
    assert response.status_code == 403, response.data
    assert MFAChallenge.objects.filter(user=staff).count() == before


def device_nonce(client):
    response = client.post(NONCE_URL, {"provider": "google", "surface": "member", "delivery": "device",
                                       "client_platform": "ios"}, format="json")
    assert response.status_code == 200, response.data
    return response.data["nonce"]


def link(client, raw, *, platform="ios"):
    return client.post(LINK, {"provider": "google", "id_token": "provider-token", "nonce": raw,
                              "client_platform": platform}, format="json")


def reauth(client):
    assert client.post("/api/v1/auth/reauth", {"password": PASSWORD}, format="json").status_code == 200


def test_member_links_provider_from_device_after_reauth(settings, monkeypatch):
    configure_google()
    user, first = member_device(settings, monkeypatch, "native-link")
    mock_claims(monkeypatch, sub="native-link-sub", email="other@example.test")
    client = _bearer(first["access"])
    raw = device_nonce(client)

    refused = link(client, raw)
    assert refused.status_code == 403 and refused.data["code"] == "recent_reauth_required"
    reauth(client)
    linked = link(client, raw)  # the refusal did not spend the nonce

    assert linked.status_code == 200, linked.data
    assert SocialIdentity.objects.filter(user=user, provider="google", provider_sub="native-link-sub").exists()
    audit = AuditLog.objects.filter(action="auth.social_identity_linked").latest("pk")
    assert audit.meta["delivery"] == "device" and audit.meta["grant_hash"]
    # Linking changes the credential fingerprint, so the proof cannot be reused.
    assert client.get("/api/v1/auth/reauth").data["verified"] is False


def test_device_link_rejects_foreign_web_and_wrong_platform_nonces(settings, monkeypatch):
    configure_google()
    user, first = member_device(settings, monkeypatch, "native-link-bound")
    second, _ = attested_login(APIClient(), user, settings, monkeypatch)
    mock_claims(monkeypatch, sub="native-link-bound-sub")
    client = _bearer(first["access"])
    reauth(client)

    assert link(client, nonce(APIClient()).data["nonce"]).status_code == 401
    assert link(client, device_nonce(_bearer(second.data["access"]))).status_code == 401
    assert link(client, device_nonce(client), platform="web").status_code == 400
    web = APIClient()
    web.force_authenticate(user)
    assert link(web, device_nonce(client), platform="web").status_code == 401
    assert not SocialIdentity.objects.filter(user=user).exists()


def test_device_link_is_throttled(settings, monkeypatch):
    from django.core.cache import cache

    configure_google()
    cache.clear()
    rest = dict(settings.REST_FRAMEWORK)
    rates = {**rest["DEFAULT_THROTTLE_RATES"], "social_link": "1/hour"}
    rest["DEFAULT_THROTTLE_RATES"] = rates
    settings.REST_FRAMEWORK = rest
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", rates)
    _user, first = member_device(settings, monkeypatch, "native-link-throttle")
    client = _bearer(first["access"])
    raw = device_nonce(client)
    assert link(client, raw).status_code == 403
    assert link(client, raw).status_code == 429


def test_device_grant_list_is_a_page(settings, monkeypatch):
    user, first = member_device(settings, monkeypatch, "native-grant-page")
    attested_login(APIClient(), user, settings, monkeypatch)
    response = _bearer(first["access"]).get("/api/v1/auth/device/grants")

    assert response.status_code == 200
    assert set(response.data) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 2 and len(response.data["results"]) == 2
    assert _bearer(first["access"]).get("/api/v1/auth/device/grants?page=2").status_code == 404


def test_device_enrollment_is_not_started_while_mobile_sessions_are_off(settings, monkeypatch):
    from apps.makerspaces.models import Makerspace

    user, first = member_device(settings, monkeypatch, "native-enroll-mobile-off")
    for space in Makerspace.objects.all():
        space.enabled_modules = [key for key in space.enabled_modules if key != "mobile"]
        space.save(update_fields=["enabled_modules"])
    response = _bearer(first["access"]).post("/api/v1/auth/mfa", {"password": PASSWORD}, format="json")

    assert response.status_code == 401
    assert not UserMFA.objects.filter(user=user).exists()
    assert _bearer(first["access"]).get("/api/v1/auth/me").status_code == 200


def test_settings_challenge_is_never_a_second_sign_in(settings, monkeypatch):
    from apps.accounts.models_devices import DeviceRefreshFamily
    from tests.accounts.mfa_helpers import enrolled

    space = make_space("native-enroll-verify-space")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"mobile"})
    space.save(update_fields=["enabled_modules"])
    user = make_user("native-enroll-verify", password=PASSWORD, access_status="active")
    _row, secret = enrolled(user)
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.data["mfa_required"] and not login.data["enrollment_required"]
    signed_in = APIClient().post("/api/v1/auth/mfa/verify",
                                 {"challenge": login.data["challenge"], "code": current_code(secret)}, format="json")
    assert signed_in.status_code == 200, signed_in.data
    grant_id = signed_in.data["device_grant"]["id"]
    families = DeviceRefreshFamily.objects.filter(grant_id=grant_id).count()

    raw = start_enrollment(_bearer(signed_in.data["access"]))
    next_code = totp(secret, int(timezone.now().timestamp() // 30) + 1)
    again = APIClient().post("/api/v1/auth/mfa/verify", {"challenge": raw, "code": next_code}, format="json")

    assert again.status_code == 401
    assert DeviceRefreshFamily.objects.filter(grant_id=grant_id).count() == families
