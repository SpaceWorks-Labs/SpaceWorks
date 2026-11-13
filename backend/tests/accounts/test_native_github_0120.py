"""Native GitHub sign-in (decision 358 A): PKCE code exchange bound to an attested device.

The redirect is the deployment's own HTTPS app link, the state lives in the social nonce
ledger (single use, device-bound, bound to the PKCE challenge), and the switches, ownership
check and account linking are the web GitHub flow's.
"""
import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.mobile_associations import association_components
from apps.accounts.models import DeviceAttestationChallenge, DeviceGrant, SocialLoginNonce
from apps.accounts.models_login_methods import PlatformLoginMethods
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.audit.models import AuditLog
from tests.accounts.account_factories import device_grant
from tests.accounts.test_github_auth import JsonResponse
from tests.accounts.test_social_first_grant import configure_native_social, issue_challenge

pytestmark = pytest.mark.django_db
START = "/api/v1/auth/social/github/device/authorize"
EXCHANGE = "/api/v1/auth/social/github/device"
BASE = "https://spaces.example.test"
REDIRECT = f"{BASE}/app/auth/github/callback"
SECRET = "github-native-secret-never-publish"
TOKEN = "github-native-access-token"


def s256(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def configured(settings):
    from cryptography.fernet import Fernet
    settings.PUBLIC_APP_BASE_URL = BASE
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    cache.clear()
    configure_native_social(settings)
    row = PlatformSocialAuthSettings.load()
    row.github_client_id = "github-oauth-client"
    row.set_github_client_secret(SECRET)
    row.save()
    return row


class AttestationEcho:
    """The external attestation verifier's answer for whatever challenge was posted."""

    status_code = 200

    def __init__(self, posted):
        self.posted = posted

    def json(self):
        keys = ("platform", "app_id", "signing_identity", "environment", "challenge")
        return {"verified": True, "subject": "attested-device-subject", **{key: self.posted[key] for key in keys}}


def attestation_echo(url, **kwargs):
    assert url == "https://attest.example.test/verify"
    return AttestationEcho(kwargs["json"])


@pytest.fixture
def github(monkeypatch):
    """GitHub and the attestation verifier share `requests.post`, so one fake routes both."""
    redeemed = []

    def post(url, **kwargs):
        if url.startswith("https://attest.example.test/"):
            return attestation_echo(url, **kwargs)
        assert url == "https://github.com/login/oauth/access_token"
        assert kwargs["data"]["redirect_uri"] == REDIRECT
        redeemed.append(kwargs["data"]["code_verifier"])
        return JsonResponse({"access_token": TOKEN, "token_type": "bearer"})

    def get(url, **kwargs):
        if url == "https://api.github.com/user":
            return JsonResponse({"id": 7654321, "name": "Native Member"})
        return JsonResponse([{"email": "native-github@example.test", "primary": True, "verified": True}])

    monkeypatch.setattr("apps.accounts.github_http.requests.post", post)
    monkeypatch.setattr("apps.accounts.github_http.requests.get", get)
    return redeemed


def start(client=None, *, verifier, challenge=None):
    body = {"client_platform": "ios", "code_challenge": s256(verifier)}
    if challenge is not None:
        body["challenge"] = challenge
    return (client or APIClient()).post(START, body, format="json")


def exchange(started, *, verifier, challenge=None, client=None, code="native-code"):
    body = {"code": code, "state": started.data["state"], "code_verifier": verifier, "client_platform": "ios"}
    if challenge is not None:
        body.update({"challenge": challenge, "attestation": {"assertion": "opaque"}})
    return (client or APIClient()).post(EXCHANGE, body, format="json")


def first_grant():
    challenge = issue_challenge(APIClient())
    verifier = secrets.token_urlsafe(48)
    started = start(verifier=verifier, challenge=challenge)
    assert started.status_code == 200, started.data
    return challenge, verifier, started


def test_first_grant_happy_path_uses_the_app_link_and_issues_an_attested_member_grant(github):
    challenge, verifier, started = first_grant()
    query = parse_qs(urlsplit(started.data["authorization_url"]).query)
    assert started.data["redirect_uri"] == REDIRECT and query["redirect_uri"] == [REDIRECT]
    assert query["code_challenge"] == [s256(verifier)] and query["code_challenge_method"] == ["S256"]
    assert query["state"] == [started.data["state"]] and query["client_id"] == ["github-oauth-client"]
    row = SocialLoginNonce.objects.get(provider="github")
    assert row.delivery == "device" and row.attestation_challenge is not None and row.consumed_at is None
    done = exchange(started, verifier=verifier, challenge=challenge)
    assert done.status_code == 200, done.data
    assert {"access", "refresh", "device_grant", "user"} <= set(done.data)
    assert github == [verifier]  # GitHub redeems the code with the app's own verifier
    user = SocialIdentity.objects.get(provider="github", provider_sub="7654321").user
    grant = DeviceGrant.objects.get(user=user)
    assert grant.authority == "member" and grant.login_method == "social"
    assert DeviceAttestationChallenge.objects.get(pk=row.attestation_challenge_id).consumed_at is not None
    assert AuditLog.objects.filter(action="auth.social_login_succeeded", meta__provider="github").exists()
    published = str((started.data, done.data, list(AuditLog.objects.values_list("meta", flat=True))))
    for value in (SECRET, TOKEN, verifier, "native-code"):
        assert value not in published


def test_replayed_state_is_refused(github):
    challenge, verifier, started = first_grant()
    assert exchange(started, verifier=verifier, challenge=challenge).status_code == 200
    replay = exchange(started, verifier=verifier, challenge=challenge)
    assert replay.status_code == 409 and replay.data["code"] == "social_device_restart_required"
    assert DeviceGrant.objects.count() == 1


def test_wrong_verifier_is_refused_and_does_not_spend_the_state(github):
    challenge, verifier, started = first_grant()
    wrong = exchange(started, verifier=secrets.token_urlsafe(48), challenge=challenge)
    assert wrong.status_code == 401 and wrong.data["code"] == "social_invalid"
    assert github == []  # never reached GitHub
    assert exchange(started, verifier=verifier, challenge=challenge).status_code == 200


def test_switch_off_refuses_start_and_exchange(github):
    challenge, verifier, started = first_grant()
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"github_enabled": False})
    cache.clear()
    assert start(verifier=verifier, challenge=issue_challenge(APIClient())).status_code == 404
    refused = exchange(started, verifier=verifier, challenge=challenge)
    assert refused.status_code == 404 and refused.data["code"] == "social_unavailable"
    assert SocialLoginNonce.objects.get(provider="github").consumed_at is None  # refused before spending it


def test_state_is_bound_to_the_attestation_challenge(github):
    challenge, verifier, started = first_grant()
    other = issue_challenge(APIClient())
    swapped = exchange(started, verifier=verifier, challenge=other)
    assert swapped.status_code == 409 and swapped.data["code"] == "social_device_restart_required"
    assert not DeviceGrant.objects.exists() and github == []


def test_existing_grant_state_cannot_be_finished_by_another_device(github):
    from tests.return_helpers import make_user
    owner = make_user("native-gh-owner", access_status="active")
    stranger = make_user("native-gh-stranger", access_status="active")
    mine = APIClient()
    mine.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_device_token_pair(owner, device_grant(owner, platform='apple'))[0]}")
    theirs = APIClient()
    theirs.credentials(
        HTTP_AUTHORIZATION=f"Bearer {issue_device_token_pair(stranger, device_grant(stranger, platform='apple'))[0]}")
    verifier = secrets.token_urlsafe(48)
    started = start(mine, verifier=verifier)
    assert started.status_code == 200, started.data
    refused = exchange(started, verifier=verifier, client=theirs)
    assert refused.status_code == 401 and refused.data["code"] == "social_invalid" and github == []


def test_first_grant_start_requires_an_attestation_challenge_and_rejects_browser_headers():
    verifier = secrets.token_urlsafe(48)
    assert start(verifier=verifier).status_code == 400
    browser = APIClient().post(START, {"client_platform": "ios", "code_challenge": s256(verifier),
                                       "challenge": issue_challenge(APIClient())},
                               format="json", HTTP_ORIGIN=BASE)
    assert browser.status_code == 403


def test_apple_association_claims_the_callback_on_the_primary_host_only():
    shared, custom = association_components("shared"), association_components("custom")
    assert {"/": "/app/auth/github/callback"} in shared
    assert {"/": "/app/auth/github/callback"} not in custom
    assert shared[-1] == {"/": "/*", "exclude": True}  # still before the catch-all exclusion
