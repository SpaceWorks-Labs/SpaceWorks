"""#196: personal access tokens and app connections act as the person, never beyond them."""
import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.apiclients.models_tokens import OAuthConsent, PersonalAccessToken, digest
from apps.audit.models import AuditLog
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db
REDIRECT = "https://app.example/cb"


def _person(name="pat-person"):
    return make_user(name, access_status=User.AccessStatus.ACTIVE)


def _create(user, **body):
    body = {"name": "Sync", "scopes": ["account:read"], "expires_in_days": 30, **body}
    return authenticated_client(user).post("/api/v1/auth/access-tokens", body, format="json")


def _bearer(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_token_is_shown_once_stored_as_digest_and_audited():
    user = _person()
    response = _create(user)
    assert response.status_code == 201, response.content
    raw = response.json()["token"]
    row = PersonalAccessToken.objects.get(pk=response.json()["id"])
    assert raw.startswith("swpat_") and row.token_digest == digest(raw)
    assert raw not in str(PersonalAccessToken.objects.filter(pk=row.pk).values().get())
    listed = authenticated_client(user).get("/api/v1/auth/access-tokens").json()
    assert "token" not in listed[0]
    assert AuditLog.objects.filter(action="access_token.created", target_id=str(row.pk)).exists()


def test_expiry_is_bounded():
    assert _create(_person("pat-b"), expires_in_days=366).status_code == 400


def test_token_reaches_own_account_reads_only_with_its_scope():
    raw = _create(_person("pat-c")).json()["token"]
    assert _bearer(raw).get("/api/v1/member/organizations/").status_code != 401
    assert _bearer(raw).post("/api/v1/member/saved-details/export/", {}, format="json").status_code == 403


def test_token_never_reaches_auth_or_credential_routes():
    raw = _create(_person("pat-d"), scopes=["account:read", "account:write"]).json()["token"]
    for path in ("/api/v1/auth/access-tokens", "/api/v1/auth/me", "/api/v1/auth/connected-apps"):
        assert _bearer(raw).get(path).status_code in (401, 403), path
    minted = _bearer(raw).post("/api/v1/auth/access-tokens", {"name": "x", "scopes": ["account:read"]}, format="json")
    assert minted.status_code in (401, 403)


def test_staff_scope_needs_a_space_where_the_person_holds_a_role():
    user = _person("pat-e")
    space = make_space("pat-space")
    assert _create(user, scopes=["staff:read"]).status_code == 400
    assert _create(user, scopes=["staff:read"], makerspace=space.pk).status_code == 400


def test_revoked_and_expired_tokens_are_refused():
    user = _person("pat-f")
    created = _create(user).json()
    assert authenticated_client(user).delete(f"/api/v1/auth/access-tokens/{created['id']}").status_code == 204
    assert AuditLog.objects.filter(action="access_token.revoked").exists()
    assert _bearer(created["token"]).get("/api/v1/member/organizations/").status_code == 401
    second = _create(user).json()
    PersonalAccessToken.objects.filter(pk=second["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert _bearer(second["token"]).get("/api/v1/member/organizations/").status_code == 401
    assert _bearer("swpat_deadbeefdeadbeef_wrong").get("/api/v1/member/organizations/").status_code == 401


def test_platform_accounts_cannot_hold_tokens():
    operator = make_user("pat-op", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    assert _create(operator).status_code == 403


def _manager(space):
    from tests.fixed_roles.helpers import assign_builtin_roles
    existing = User.objects.filter(username=f"oauth-mgr-{space.slug}").first()
    if existing is not None:  # one manager per space across repeated registrations in a test
        return existing
    user = make_user(f"oauth-mgr-{space.slug}", access_status=User.AccessStatus.ACTIVE, account_kind="staff",
                     staff_makerspace=space)
    assign_builtin_roles(user, space, "space_manager")
    return user


def _register(space, **body):
    body = {"name": "Calendar app", "client_type": "confidential", "redirect_uris": [REDIRECT],
            "allowed_scopes": ["account:read"], **body}
    return authenticated_client(_manager(space)).post(f"/api/v1/admin/makerspace/{space.pk}/oauth-apps", body,
                                                      format="json")


def _query(app, scope="account:read", state="s1"):
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, urlencode({"response_type": "code", "client_id": app["client_id"], "redirect_uri": REDIRECT,
                                "scope": scope, "state": state, "code_challenge": challenge,
                                "code_challenge_method": "S256"})


def test_app_registration_shows_secret_once_and_refuses_bad_input():
    space = make_space("oauth-a")
    created = _register(space)
    assert created.status_code == 201 and created.json()["client_secret"]
    assert _register(space, name="b", redirect_uris=["http://evil.example/cb"]).status_code == 400
    assert _register(space, name="c", allowed_scopes=["admin:*"]).status_code == 400
    assert AuditLog.objects.filter(action="oauth_app.created").exists()


def test_authorization_code_pkce_flow_consent_use_rotation_and_disconnect():
    app = _register(make_space("oauth-b")).json()
    person = _person("oauth-person")
    verifier, query = _query(app)
    api = authenticated_client(person)
    preview = api.get(f"/api/v1/auth/oauth/authorize?{query}")
    assert preview.status_code == 200 and preview.json()["app_name"] == "Calendar app"
    without_pkce = urlencode({"response_type": "code", "client_id": app["client_id"], "redirect_uri": REDIRECT,
                              "scope": "account:read"})
    assert api.get(f"/api/v1/auth/oauth/authorize?{without_pkce}").status_code == 400
    decided = api.post(f"/api/v1/auth/oauth/authorize?{query}", {"allow": True}, format="json")
    assert decided.status_code == 200, decided.content
    code = parse_qs(urlsplit(decided.json()["redirect_to"]).query)["code"][0]
    tokens = APIClient().post("/api/v1/oauth/token/", {
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "client_id": app["client_id"], "client_secret": app["client_secret"], "code_verifier": verifier})
    assert tokens.status_code == 200, tokens.content
    access, refresh = tokens.json()["access_token"], tokens.json()["refresh_token"]
    assert access.startswith("swoa_")
    assert _bearer(access).get("/api/v1/member/organizations/").status_code != 401
    assert _bearer(access).get("/api/v1/auth/access-tokens").status_code in (401, 403)
    rotated = APIClient().post("/api/v1/oauth/token/", {
        "grant_type": "refresh_token", "refresh_token": refresh, "client_id": app["client_id"],
        "client_secret": app["client_secret"]})
    assert rotated.status_code == 200 and rotated.json()["refresh_token"] != refresh
    assert [row["app_name"] for row in api.get("/api/v1/auth/connected-apps").json()] == ["Calendar app"]
    assert api.delete(f"/api/v1/auth/connected-apps/{app['id']}").status_code == 204
    assert not OAuthConsent.objects.filter(user=person).exists()
    assert _bearer(rotated.json()["access_token"]).get("/api/v1/member/organizations/").status_code == 401


def test_denied_consent_returns_access_denied_to_the_app():
    app = _register(make_space("oauth-c")).json()
    _verifier, query = _query(app, state="s2")
    decided = authenticated_client(_person("oauth-deny")).post(f"/api/v1/auth/oauth/authorize?{query}",
                                                               {"allow": False}, format="json")
    assert decided.status_code == 200 and "error=access_denied" in decided.json()["redirect_to"]


def test_app_cannot_ask_for_unregistered_scopes_and_switched_off_apps_stop():
    space = make_space("oauth-d")
    app = _register(space).json()
    _verifier, wide = _query(app, scope="staff:write")
    person = authenticated_client(_person("oauth-wide"))
    assert person.get(f"/api/v1/auth/oauth/authorize?{wide}").status_code == 400
    manager = authenticated_client(_manager(space))
    assert manager.patch(f"/api/v1/admin/oauth-apps/{app['id']}", {"is_active": False}, format="json").status_code == 200
    _verifier, query = _query(app)
    assert person.get(f"/api/v1/auth/oauth/authorize?{query}").status_code == 400


def test_protocol_endpoints_are_outside_api_client_reach():
    from apps.apiclients.scope_registry_coverage import out_of_scope_reason
    assert out_of_scope_reason("api/v1/oauth/token/")
