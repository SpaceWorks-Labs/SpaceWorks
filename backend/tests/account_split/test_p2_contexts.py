"""Same-person principals never choose, refresh, or revoke each other's sessions."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.surface_policy import validate_account_token
from apps.makerspaces.models import Makerspace
from .p1_helpers import staff

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skip(reason="U-A1/U-B: one account per person - member, staff and platform principals can no longer share an e-mail (uniq_person_email), and login has only the member/platform surfaces with no per-makerspace staff cookie; the premise of this module is retired"),
]
PASSWORD = "Separate accounts password 965!"
ORIGIN = "http://localhost:5000"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
HEADERS = {"HTTP_ORIGIN": ORIGIN, "HTTP_X_REFRESH_CSRF": "1"}


@pytest.fixture
def principals(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    a, b = [Makerspace.objects.create(name=slug, slug=slug) for slug in ("context-a", "context-b")]
    email = "same-person@example.test"
    member = User.objects.create_user("member", email=email, password=PASSWORD)
    staff_a = staff(a, "staff-a", email=email, password=PASSWORD)[0]
    staff_b = staff(b, "staff-b", email=email, password=PASSWORD)[0]
    platform = User.objects.create_superuser("platform", email=email, password=PASSWORD)
    return member, staff_a, staff_b, platform


def login(client, user, identifier=None, **extra):
    payload = {"username": identifier or user.email, "password": PASSWORD, "context": user.account_kind}
    if user.account_kind == "staff":
        payload["makerspace"] = user.staff_makerspace.slug
    payload.update(extra)
    return client.post(LOGIN, payload, format="json", HTTP_ORIGIN=ORIGIN)


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("identifier", ["email", "username"])
def test_login_resolves_same_email_only_in_selected_namespace(principals, index, identifier):
    user = principals[index]
    response = login(APIClient(), user, getattr(user, identifier))
    assert response.status_code == 200, response.data
    assert response.data["user"]["id"] == user.pk
    assert response.data["user"]["account_kind"] == user.account_kind
    assert response.data["user"]["must_change_password"] is False
    claims = AccessToken(response.data["access"])
    assert claims["kind"] == user.account_kind
    assert claims.get("makerspace") == user.staff_makerspace_id


def test_staff_login_requires_slug_and_refuses_foreign_username(principals):
    _member, a, b, _platform = principals
    client = APIClient()
    assert client.post(LOGIN, {"username": a.username, "password": PASSWORD, "context": "staff"},
                       format="json").status_code == 400
    wrong = login(client, a, a.username, makerspace=b.staff_makerspace.slug)
    bad_password = login(client, a, a.username, password="bad")
    assert wrong.status_code == bad_password.status_code == 401
    assert wrong.data == bad_password.data
    assert login(client, a, a.username, surface="member").status_code == 401
    assert login(client, _member, _member.username, context="staff",
                 makerspace=a.staff_makerspace.slug).status_code == 401


def test_custom_origin_must_match_staff_makerspace_and_platform_origin(principals):
    _member, a, b, platform = principals
    space = b.staff_makerspace
    space.frontend_domain = "context-b.example.test"
    space.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    for user in (a, platform):
        payload = {"username": user.username, "password": PASSWORD, "context": user.account_kind}
        if user == a:
            payload["makerspace"] = a.staff_makerspace.slug
        assert APIClient().post(LOGIN, payload, format="json",
                                HTTP_ORIGIN="https://context-b.example.test").status_code == 401


def test_each_cookie_rotates_and_logout_leaves_other_contexts_alive(principals):
    client = APIClient()
    names = ["refresh_token", "refresh_token_staff_context-a", "refresh_token_staff_context-b",
             "refresh_token_platform"]
    contexts = ["member", "staff:context-a", "staff:context-b", "platform"]
    for user in principals:
        assert login(client, user).status_code == 200
    original = {name: client.cookies[name].value for name in names}
    for user, context, name in zip(principals, contexts, names):
        other_values = {key: client.cookies[key].value for key in names if key != name}
        response = client.post(REFRESH, {"context": context}, format="json", **HEADERS)
        assert response.status_code == 200, response.data
        assert response.data["user"]["id"] == user.pk
        assert client.cookies[name].value != original[name]
        assert all(client.cookies[key].value == value for key, value in other_values.items())
    staff_access = client.post(REFRESH, {"context": contexts[1]}, format="json", **HEADERS).data["access"]
    assert client.post(LOGOUT, {"context": contexts[1]}, format="json", **HEADERS).status_code == 204
    assert client.cookies[names[1]].value == ""
    for index in (0, 2, 3):
        assert client.post(REFRESH, {"context": contexts[index]}, format="json", **HEADERS).status_code == 200
    bearer = APIClient()
    bearer.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_access}")
    assert bearer.get("/api/v1/auth/me", HTTP_ORIGIN=ORIGIN).status_code == 401


def test_wrong_cookie_kind_or_tenant_is_never_consumed(principals):
    member, a, b, platform = principals
    client = APIClient()
    login(client, member)
    raw = client.cookies["refresh_token"].value
    client.cookies["refresh_token_staff_context-a"] = raw
    for path in (REFRESH, LOGOUT):
        assert client.post(path, {"context": "staff:context-a"}, format="json", **HEADERS).status_code == 401
    # Failed cross-context use must not consume the valid member refresh family.
    assert client.post(REFRESH, {"context": "member"}, format="json", **HEADERS).status_code == 200


@pytest.mark.parametrize("index", range(4))
def test_pre_kind_token_rejected_on_access_and_refresh(principals, index):
    from rest_framework.exceptions import AuthenticationFailed
    user = principals[index]
    token = SpaceWorksRefreshToken.for_user(user)
    del token["kind"]
    with pytest.raises(AuthenticationFailed):
        validate_account_token(user, token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    assert client.get("/api/v1/auth/me", HTTP_ORIGIN=ORIGIN).status_code == 401
    from apps.accounts.serializers_refresh import SpaceWorksTokenRefreshSerializer
    serializer = SpaceWorksTokenRefreshSerializer(data={"refresh": str(token)})
    with pytest.raises(AuthenticationFailed):
        serializer.is_valid(raise_exception=True)


@pytest.mark.parametrize("known", [False, True])
def test_browser_password_refusal_keeps_axes_failure_accounting(known, settings):
    from axes.models import AccessAttempt
    settings.AXES_ENABLED = True
    username = "browser-known" if known else "browser-unknown"
    if known:
        User.objects.create_user(username, password=PASSWORD)
    response = APIClient().post(LOGIN, {"username": username, "password": "wrong", "context": "member"},
                                format="json")
    assert response.status_code == 401
    assert AccessAttempt.objects.get(username=username).failures_since_start == 1
