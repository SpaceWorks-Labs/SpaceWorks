"""Kind-bound first/second factors and the member-only native password door."""

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from django.test import Client, RequestFactory
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import UntypedToken

from apps.accounts import mfa_challenges, reauthentication, reauthentication_intents
from apps.accounts.auth_backends import SpaceWorksModelBackend
from apps.accounts.login_methods_validation import validate_login_methods
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import PlatformLoginMethods, User
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.makerspaces.models import Makerspace
from tests.account_split.p1_helpers import staff
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_device_auth import attested_login
from tests.accounts.test_reauthentication import request as reauth_request

pytestmark = pytest.mark.django_db
PASSWORD = "Account split MFA password 527!"
ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def configuration(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]


def accounts():
    space = Makerspace.objects.create(name="MFA account kinds", slug="mfa-account-kinds")
    member = User.objects.create_user("kind-member", email="shared@example.test", password=PASSWORD)
    worker, _ = staff(space, "kind-staff", password=PASSWORD, email="kind-staff@example.test")
    platform = User.objects.create_superuser("kind-platform", email="kind-platform@example.test", password=PASSWORD)
    return space, member, worker, platform


@pytest.mark.parametrize("kind", ["member", "staff", "platform"])
def test_mfa_completion_keeps_first_factor_kind_and_context_cookie(kind):
    space, member, worker, platform = accounts()
    user = {"member": member, "staff": worker, "platform": platform}[kind]
    _, secret = enrolled(user)
    client = APIClient()
    # U-B: browser sessions are person or platform only; a staff role is the person's.
    payload = {"username": user.email, "password": PASSWORD, "context": "platform" if kind == "platform" else "person"}
    first = client.post("/api/v1/auth/login", payload, format="json", HTTP_ORIGIN=ORIGIN)
    assert first.status_code == 200 and first.data["mfa_required"]
    pending = MFAChallenge.objects.get(user=user)
    person_kind = "platform" if kind == "platform" else "person"  # U-A1: staff-track holders are people
    assert pending.context["kind"] == person_kind
    assert pending.context.get("makerspace") in (None, str(space.pk) if kind == "staff" else None)
    completed = client.post("/api/v1/auth/mfa/verify", {
        "challenge": first.data["challenge"],
        "code": totp(secret, int(timezone.now().timestamp() // 30)),
        "surface": "member",  # Caller cannot rewrite the stored login context.
    }, format="json", HTTP_ORIGIN=ORIGIN)
    assert completed.status_code == 200
    claims = UntypedToken(completed.data["access"])
    assert claims["kind"] == person_kind
    if kind == "staff":
        assert str(claims.get("makerspace") or space.pk) == str(space.pk)
    cookie = "refresh_token_platform" if kind == "platform" else "refresh_token"
    assert completed.cookies[cookie].value


@pytest.mark.parametrize("change", ["kind", "makerspace", "credential_generation", "inactive"])
def test_pending_mfa_revalidates_identity_and_live_account(change):
    _, user, _, _ = accounts()
    enrolled(user)
    raw = mfa_challenges.start(user, context={"surface": "member", "origin": ""})["challenge"]
    row = MFAChallenge.objects.get(user=user)
    if change == "inactive":
        User.objects.filter(pk=user.pk).update(is_active=False)
    else:
        row.context[change] = {"kind": "staff", "makerspace": "999", "credential_generation": 999}[change]
        row.save(update_fields=["context"])
    response = APIClient().post("/api/v1/auth/mfa/verify", {
        "challenge": raw, "code": "000000"}, format="json")
    assert response.status_code == 401
    row.refresh_from_db()
    assert row.consumed_at is None and row.attempts == 0


def test_native_email_lookup_does_not_choose_staff_or_platform(settings, monkeypatch):
    _, member, worker, platform = accounts()
    # Resolve the shared email to the member before calling Django authentication.
    client = APIClient()
    from tests.accounts.test_device_auth import configure_apple, mock_apple_provider, CHALLENGE, LOGIN
    configure_apple(settings)
    result = client.post(CHALLENGE, {"platform": "apple", "app_id": "org.spaceworks.app",
                                    "environment": "development"}, format="json")
    raw = result.data["challenge"]
    mock_apple_provider(monkeypatch, raw)
    response = client.post(LOGIN, {"username": member.email, "password": PASSWORD,
        "platform": "apple", "app_id": "org.spaceworks.app", "environment": "development",
        "challenge": raw, "attestation": {"assertion": "opaque"}}, format="json")
    assert response.status_code == 200
    assert str(UntypedToken(response.data["access"])["user_id"]) == str(member.pk)
    # attested_login sends the staff context for staff users, which is a legitimate staff
    # login; the property here is that the default member door never picks them.
    for user in (platform,):  # a staff-track holder is a person (U-A1) and may use the door
        result = client.post(CHALLENGE, {"platform": "apple", "app_id": "org.spaceworks.app",
                                        "environment": "development"}, format="json")
        mock_apple_provider(monkeypatch, result.data["challenge"])
        response = client.post(LOGIN, {"username": user.username, "password": PASSWORD,
            "platform": "apple", "app_id": "org.spaceworks.app", "environment": "development",
            "challenge": result.data["challenge"], "attestation": {"assertion": "opaque"}}, format="json")
        assert response.status_code == 401


@pytest.mark.parametrize("kind", ["platform"])  # staff-track holders are people (U-A1)
def test_device_issuer_and_social_reauthentication_refuse_privileged_accounts(kind):
    _, _, worker, platform = accounts()
    user = worker if kind == "staff" else platform
    # Native staff grants are real (password + MFA + attestation), but never via a member grant.
    with pytest.raises(AuthenticationFailed):
        issue_device_token_pair(user, SimpleNamespace(user_id=user.pk, authority="member"))
    req = reauth_request(user)
    with pytest.raises(AuthenticationFailed):
        reauthentication_intents.start_social(req, provider="google", redirect_uri=ORIGIN)
    if kind == "platform":
        client = APIClient()
        client.force_authenticate(user)
        assert client.get("/api/v1/auth/device/grants").status_code == 401


def test_reauthentication_fingerprint_and_intents_bind_account_kind():
    _, member, _, _ = accounts()
    original = reauthentication.versions(member)["credential_fingerprint"]
    member.account_kind = "staff"  # In-memory assertion; kind mutation is DB-guarded.
    assert reauthentication.versions(member)["credential_fingerprint"] != original
    member.refresh_from_db()
    req = reauth_request(member)
    raw, row = reauthentication_intents._new(req, "social_reauth")
    row.context["kind"] = "platform"
    row.save(update_fields=["context"])
    from django.db import transaction
    with transaction.atomic(), pytest.raises(AuthenticationFailed):
        reauthentication_intents._consume(req, raw, "social_reauth")


def test_member_method_switches_preserve_platform_and_staff_password_login():
    space, _, worker, platform = accounts()
    policy = PlatformLoginMethods(password_enabled=False, social_enabled=False)
    validate_login_methods(policy)
    policy.save()
    body = {"username": platform.username, "password": PASSWORD, "context": "platform"}
    result = APIClient().post("/api/v1/auth/login", body, format="json", HTTP_ORIGIN=ORIGIN)
    assert result.status_code == 200 and result.data["access"]
    # U-A1: a staff-track holder is a person, so the member password switch governs them too.
    body = {"username": worker.username, "password": PASSWORD, "context": "person"}
    refused = APIClient().post("/api/v1/auth/login", body, format="json", HTTP_ORIGIN=ORIGIN)
    assert refused.status_code != 200 and "access" not in refused.data


def test_disabled_member_password_door_does_not_enumerate_account_namespaces():
    _, member, _, platform = accounts()
    PlatformLoginMethods.objects.create(password_enabled=False)
    client = APIClient()
    responses = [client.post("/api/v1/auth/login", {
        "username": identifier, "password": PASSWORD, "context": "member",
    }, format="json") for identifier in ("unknown-person", member.username, platform.username)]
    assert all(response.status_code == 403 for response in responses)
    assert responses[0].data == responses[1].data == responses[2].data


def test_control_password_backend_uses_platform_namespace_and_sessions_bind_kind():
    _, member, worker, platform = accounts()
    backend = SpaceWorksModelBackend()
    req = RequestFactory().post("/control/login/")
    assert backend.authenticate(req, username=platform.email, password=PASSWORD) == platform
    for user in (member, worker):
        assert backend.authenticate(req, username=user.username, password=PASSWORD) is None
    client = Client()
    assert client.login(username=platform.username, password=PASSWORD)
    assert client.session["account_kind"] == "platform"
    session = client.session
    session.pop("account_kind")
    session.save()
    assert client.get("/control/").url == "/mfa/control/"


@pytest.mark.django_db(transaction=True)
def test_native_old_password_cannot_pass_a_concurrent_reset():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from django.db import close_old_connections, transaction
    from apps.accounts.services_device_login import password_login, DevicePasswordRejected

    user = User.objects.create_user("native-reset-race", password=PASSWORD)
    started, completed = Event(), Event()

    def attempt():
        close_old_connections()
        started.set()
        try:
            request = RequestFactory().post("/api/v1/auth/device/login")
            # Attestation has completed before this transactional password boundary.
            password_login(request, {"username": user.username, "password": PASSWORD, "context": "member",
                                     "authority": "member"},
                           None, None)
            return "issued"
        except DevicePasswordRejected:
            return "refused"
        finally:
            completed.set()
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=user.pk)
            locked.set_password("Replacement password 865!")
            locked.save(update_fields=["password"])
            future = pool.submit(attempt)
            assert started.wait(timeout=5)
            assert not completed.wait(timeout=0.5), "Password verification must wait for the reset"
        assert future.result(timeout=10) == "refused"
    assert not user.device_grants.exists()


@pytest.mark.parametrize("known", [False, True])
def test_native_password_rejection_preserves_axes_failure_accounting(known, settings, monkeypatch):
    from axes.models import AccessAttempt

    settings.AXES_ENABLED = True
    if known:
        user = User.objects.create_user("native-known-failure", password=PASSWORD)
    else:
        user = SimpleNamespace(username="native-unknown-failure", account_kind="member")
    response, _ = attested_login(APIClient(), user, settings, monkeypatch, password="wrong-password")
    assert response.status_code == 401
    attempt = AccessAttempt.objects.get(username=user.username)
    assert attempt.failures_since_start == 1
