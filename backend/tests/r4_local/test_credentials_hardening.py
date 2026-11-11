"""R4 security: one-time secrets are never cached, OAuth registration and PKCE are strict,
account sessions are a credential route, and /control/ token rows are view-only. Local only."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import pytest
from django.contrib import admin
from django.test import RequestFactory

from tests.api_r2.test_person_credentials import REDIRECT, _bearer, _create, _manager, _person, _register
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def test_personal_token_and_app_secret_responses_are_no_store():
    created = _create(_person("r4-pat"))
    assert created.status_code == 201 and created["Cache-Control"] == "private, no-store"
    app = _register(make_space("r4-oauth-a"))
    assert app.status_code == 201 and app["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("uri", [
    "http://localhost.evil.example/cb", "https://u@h.example/cb", "http://10.0.0.5/cb",
    "https://h.example/cb#frag", "ftp://h.example/cb", "https://[::1/cb",
])
def test_bad_redirect_uris_are_400_not_500(uri):
    response = _register(make_space(f"r4-uri-{abs(hash(uri)) % 10_000}"), redirect_uris=[uri])
    assert response.status_code == 400, (uri, response.status_code, response.content)


@pytest.mark.parametrize("invalid_uri", [
    f"{REDIRECT} http://other.example/cb",
    f"{REDIRECT}\thttp://other.example/cb",
    f"{REDIRECT}\nhttp://other.example/cb",
    f"{REDIRECT}\u00a0http://other.example/cb",
    f"{REDIRECT}\x00suffix",
    f"{REDIRECT} ",
    f"{REDIRECT}#",
])
def test_redirect_uri_storage_cannot_split_or_hide_invalid_characters(invalid_uri):
    space = make_space("r4-oauth-redirect")
    manager = authenticated_client(_manager(space))
    list_url = f"/api/v1/admin/makerspace/{space.pk}/oauth-apps"
    redirects = [REDIRECT, "https://app.example/encoded%20path?value=%23"]
    body = {"name": "Calendar app", "client_type": "public", "redirect_uris": redirects,
            "allowed_scopes": ["account:read"]}
    created = manager.post(list_url, body, format="json")
    assert created.status_code == 201, created.content
    assert created.json()["redirect_uris"] == redirects

    refused_create = manager.post(list_url, {**body, "redirect_uris": [invalid_uri]}, format="json")
    assert refused_create.status_code == 400, refused_create.content
    detail_url = f"/api/v1/admin/oauth-apps/{created.json()['id']}"
    refused_update = manager.patch(detail_url, {"redirect_uris": [invalid_uri]}, format="json")
    assert refused_update.status_code == 400, refused_update.content

    listed = manager.get(list_url)
    assert listed.status_code == 200, listed.content
    assert [row["redirect_uris"] for row in listed.json()] == [redirects]


def test_loopback_redirects_are_allowed_and_scopes_only_update_works():
    space = make_space("r4-oauth-b")
    manager = authenticated_client(_manager(space))
    redirects = ["http://127.0.0.1:8765/cb", "http://localhost/cb"]
    created = manager.post(
        f"/api/v1/admin/makerspace/{space.pk}/oauth-apps",
        {"name": "Calendar app", "client_type": "confidential", "redirect_uris": redirects,
         "allowed_scopes": ["account:read"]},
        format="json",
    )
    assert created.status_code == 201, created.content
    changed = manager.patch(f"/api/v1/admin/oauth-apps/{created.json()['id']}",
                            {"allowed_scopes": ["account:read"]}, format="json")
    assert changed.status_code == 200, changed.content
    assert changed.json()["redirect_uris"] == redirects


def _authorize(app, method):
    verifier = secrets.token_urlsafe(48)
    if method == "S256":
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    else:
        challenge = verifier
    params = {"response_type": "code", "client_id": app["client_id"], "redirect_uri": REDIRECT,
              "scope": "account:read", "state": "s", "code_challenge": challenge}
    if method:
        params["code_challenge_method"] = method
    return urlencode(params)


def test_only_s256_pkce_is_accepted():
    app = _register(make_space("r4-oauth-c")).json()
    person = authenticated_client(_person("r4-pkce"))
    assert person.get(f"/api/v1/auth/oauth/authorize?{_authorize(app, 'S256')}").status_code == 200
    assert person.get(f"/api/v1/auth/oauth/authorize?{_authorize(app, 'plain')}").status_code == 400
    assert person.get(f"/api/v1/auth/oauth/authorize?{_authorize(app, None)}").status_code == 400


def test_a_token_cannot_list_or_revoke_account_sessions():
    raw = _create(_person("r4-sessions"), scopes=["account:read", "account:write"]).json()["token"]
    base = "/api/v1/member/makerspaces/1/account/sessions"
    assert _bearer(raw).get(base).status_code == 403
    assert _bearer(raw).delete(f"{base}/abc").status_code == 403


def test_control_token_rows_are_view_only():
    from oauth2_provider.models import AccessToken, Grant, IDToken, RefreshToken

    request = RequestFactory().get("/control/")
    for model in (AccessToken, RefreshToken, Grant, IDToken):
        model_admin = admin.site._registry[model]
        assert model_admin.has_change_permission(request) is False
        assert model_admin.has_add_permission(request) is False
    assert "revoke_tokens" in admin.site._registry[AccessToken].actions
