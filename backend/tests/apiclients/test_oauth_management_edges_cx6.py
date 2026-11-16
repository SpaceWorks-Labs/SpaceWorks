"""OAuth management exercises serializers, transactions, authority and DOT over HTTP."""
from urllib.parse import urlencode

import pytest
from oauth2_provider.models import get_application_model
from django.utils import timezone

from apps.apiclients.models_tokens import OAuthAppRegistration, OAuthConsent
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_profiles import PublicHandle
from tests.accounts.account_factories import make_staff
from tests.accounts.ua1_helpers import person
from tests.api_r2.test_person_credentials import _query
from tests.return_helpers import authenticated_client
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/oauth-apps/"


@pytest.fixture
def manager():
    space = Makerspace.objects.create(name="OAuth edges", slug="cx6-oauth-edges")
    actor = make_staff(space, username="cx6-oauth-manager")
    PublicHandle.objects.create(user=actor, handle="cx6.oauth.manager", changed_at=timezone.now())
    return space, actor, bearer_client(actor, recent=True)


def register(manager, **changes):
    space, _, api = manager
    return api.post(f"/api/v1/admin/makerspace/{space.pk}/oauth-apps", {
        "name": "Calendar app", "client_type": "public", "redirect_uris": ["https://app.example/cb"],
        "allowed_scopes": ["account:read"], **changes}, format="json")


@pytest.mark.parametrize("uri,message", [
    ("https://app.example/cb#fragment", "Redirect URIs cannot contain whitespace, control characters or fragments."),
    ("https://app.example/cb\n", "Redirect URIs cannot contain whitespace, control characters or fragments."),
    ("https://app.example/cb\x7f", "Redirect URIs cannot contain whitespace, control characters or fragments."),
    ("http://localhost.evil.example/cb", "Use https:// redirect URIs (http:// only for localhost, 127.0.0.1 or [::1])."),
    ("https://user@app.example/cb", "Use https:// redirect URIs (http:// only for localhost, 127.0.0.1 or [::1])."),
    ("https://app.example:99999/cb", "Origin port is invalid."),
])
def test_bad_redirect_is_a_typed_validation_refusal_with_no_rows_or_audit(manager, uri, message):
    response = register(manager, redirect_uris=[uri])
    assert response.status_code == 400
    assert response.data["redirect_uris"].code == "invalid"
    assert str(response.data["redirect_uris"]) == message
    assert OAuthAppRegistration.objects.count() == 0
    assert AuditLog.objects.filter(action="oauth_app.created").count() == 0


@pytest.mark.parametrize("uri", ["http://localhost:8080/cb", "http://127.0.0.1:8080/cb", "http://[::1]:8080/cb"])
def test_loopback_redirects_are_allowed_and_public_apps_have_no_secret(manager, uri):
    response = register(manager, redirect_uris=[uri])
    assert response.status_code == 201
    assert response.data["redirect_uris"] == [uri]
    assert response.data["client_secret"] == ""
    assert response["Cache-Control"] == "private, no-store"
    app = get_application_model().objects.get(pk=response.data["id"])
    assert (app.client_type, app.redirect_uris, app.skip_authorization) == ("public", uri, False)


def test_list_update_and_delete_never_reveal_the_confidential_secret(manager):
    space, actor, api = manager
    created = register(manager, client_type="confidential")
    assert created.status_code == 201
    assert created.data["client_secret"]
    pk = created.data["id"]
    listing = api.get(f"/api/v1/admin/makerspace/{space.pk}/oauth-apps")
    assert listing.status_code == 200
    assert [row["id"] for row in listing.data] == [pk]
    assert "client_secret" not in listing.data[0]
    changed = api.patch(BASE + str(pk), {"name": "Renamed", "allowed_scopes": ["account:write"],
        "redirect_uris": ["https://second.example/cb"], "is_active": False}, format="json")
    assert changed.status_code == 200
    assert (changed.data["name"], changed.data["redirect_uris"], changed.data["allowed_scopes"],
            changed.data["is_active"]) == ("Renamed", ["https://second.example/cb"], ["account:write"], False)
    assert "client_secret" not in changed.data
    update = AuditLog.objects.get(action="oauth_app.updated", target_id=str(pk))
    assert (update.actor_id, update.makerspace_id, update.meta) == (
        actor.pk, space.pk, {"scopes": ["account:write"], "is_active": False})
    assert api.delete(BASE + str(pk)).status_code == 204
    assert OAuthAppRegistration.objects.filter(application_id=pk).count() == 0
    assert get_application_model().objects.filter(pk=pk).count() == 0
    assert AuditLog.objects.filter(action="oauth_app.deleted", target_id=str(pk)).count() == 1
    repeated = api.delete(BASE + str(pk))
    assert (repeated.status_code, repeated.data["code"]) == (404, "not_found")


def test_invalid_scope_patch_rolls_back_application_changes(manager):
    _, _, api = manager
    created = register(manager)
    assert created.status_code == 201
    pk = created.data["id"]
    response = api.patch(BASE + str(pk), {"name": "Must roll back", "allowed_scopes": ["unknown:scope"]}, format="json")
    assert response.status_code == 400
    assert response.data["allowed_scopes"].code == "invalid"
    assert str(response.data["allowed_scopes"]) == "Unknown scope(s): unknown:scope."
    assert get_application_model().objects.get(pk=pk).name == "Calendar app"
    assert OAuthAppRegistration.objects.get(application_id=pk).allowed_scopes == ["account:read"]
    assert AuditLog.objects.filter(action="oauth_app.updated", target_id=str(pk)).count() == 0


def test_another_tenants_manager_cannot_list_change_or_delete_apps(manager):
    space, _, _ = manager
    created = register(manager)
    assert created.status_code == 201
    other = Makerspace.objects.create(name="Other OAuth", slug="cx6-oauth-other")
    api = authenticated_client(make_staff(other, username="cx6-other-oauth-manager"))
    responses = [api.get(f"/api/v1/admin/makerspace/{space.pk}/oauth-apps"),
                 api.patch(BASE + str(created.data["id"]), {"is_active": False}, format="json"),
                 api.delete(BASE + str(created.data["id"]))]
    assert [response.status_code for response in responses] == [404, 404, 404]
    assert [response.data["code"] for response in responses] == ["not_found", "not_found", "not_found"]
    assert OAuthAppRegistration.objects.get(application_id=created.data["id"]).is_active is True


def test_staff_scope_consent_requires_the_persons_staff_role(manager):
    created = register(manager, allowed_scopes=["staff:read"])
    assert created.status_code == 201
    _, query = _query(created.data, scope="staff:read")
    user = person("cx6-oauth-no-staff")
    PublicHandle.objects.create(user=user, handle="cx6.oauth.no.staff", changed_at=timezone.now())
    response = bearer_client(user, recent=True).post("/api/v1/auth/oauth/authorize?" + query,
                                                     {"allow": True}, format="json")
    assert (response.status_code, response.data["code"]) == (400, "invalid")
    assert str(response.data["detail"]) == "This app asks for staff access in a space where you hold no role."
    assert OAuthConsent.objects.filter(user=user).count() == 0
    assert AuditLog.objects.filter(action="oauth_consent.granted", actor=user).count() == 0


def test_plain_pkce_and_an_invalid_client_are_exact_validation_errors(manager):
    created = register(manager)
    assert created.status_code == 201
    user = person("cx6-oauth-invalid-proof")
    api = bearer_client(user, recent=True)
    params = {"client_id": created.data["client_id"], "response_type": "code", "redirect_uri": "https://app.example/cb",
              "scope": "account:read", "code_challenge": "x" * 43, "code_challenge_method": "plain"}
    plain = api.get("/api/v1/auth/oauth/authorize?" + urlencode(params))
    assert (plain.status_code, plain.data["code"]) == (400, "invalid")
    assert str(plain.data["detail"]) == "Use PKCE with code_challenge_method=S256."
    params.update(client_id="missing-app", code_challenge_method="S256")
    invalid = api.get("/api/v1/auth/oauth/authorize?" + urlencode(params))
    assert (invalid.status_code, invalid.data["code"]) == (400, "invalid")
    assert OAuthConsent.objects.filter(user=user).count() == 0


def test_disconnect_is_owner_scoped_and_replay_emits_no_second_audit(manager):
    created = register(manager)
    assert created.status_code == 201
    app = get_application_model().objects.get(pk=created.data["id"])
    owner, other = person("cx6-oauth-owner"), person("cx6-oauth-peer")
    PublicHandle.objects.create(user=owner, handle="cx6.oauth.owner", changed_at=timezone.now())
    OAuthConsent.objects.create(user=owner, application=app, scopes=["account:read"])
    OAuthConsent.objects.create(user=other, application=app, scopes=["account:read"])
    api = bearer_client(owner)
    listing = api.get("/api/v1/auth/connected-apps")
    assert listing.status_code == 200
    assert [row["application_id"] for row in listing.data] == [app.pk]
    path = f"/api/v1/auth/connected-apps/{app.pk}"
    assert api.delete(path).status_code == 204
    assert api.delete(path).status_code == 204
    assert list(OAuthConsent.objects.values_list("user_id", flat=True)) == [other.pk]
    assert AuditLog.objects.filter(action="oauth_consent.revoked", actor=owner, target_id=str(app.pk)).count() == 1
