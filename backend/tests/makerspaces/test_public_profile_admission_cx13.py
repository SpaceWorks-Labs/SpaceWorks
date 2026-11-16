"""549 / R1: enforced API-client admission uses the live public card predicate."""
from datetime import datetime, timezone as dt_timezone

import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import resolve
from rest_framework.test import APIClient

from apps.apiclients.models import ApiClient
from apps.apiclients.scope_registry import lookup, resolve_target
from apps.apiclients.scope_registry_public_pages import is_global_target
from apps.makerspaces.models import AccountProfile, Makerspace, MakerspaceMembership, MinorProfile
from tests.apiclients.test_staff_reads_lane_f import read
from tests.makerspaces.test_public_profile_cx13 import BASE, add_membership, person

pytestmark = pytest.mark.django_db
SHARED = "/api/v1/public/page-handles/cx13.maker/"


@pytest.fixture
def enforced(settings):
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    cache.clear()
    yield
    cache.clear()


def issue(space=None, scopes=None, **kwargs):
    return ApiClient.issue(label="CX13 profile reader", makerspace=space,
                           client_type="server", scopes=scopes or ["public:read"],
                           allowed_origins=["https://foreign.example.test"], **kwargs)


@pytest.mark.parametrize("transport", ["signed", "browser"])
@pytest.mark.parametrize("condition", ["opt_out", "no_membership", "no_profile", "restricted", "suspended", "minor"])
def test_enforced_clients_reach_cards_and_shared_handles(person, enforced, condition, transport):
    space = None
    if condition != "no_membership":
        space, _ = add_membership(person)
    if condition == "no_profile":
        AccountProfile.objects.filter(user=person).delete()
    elif condition in {"restricted", "suspended"}:
        type(person).objects.filter(pk=person.pk).update(access_status=condition)
    elif condition == "minor":
        MinorProfile.objects.create(user=person, makerspace=space, declared_under_age=True)
    if transport == "signed":
        client, secret = issue(space)
        fetch = lambda path: read(client, secret, path)
    else:
        client, _ = ApiClient.issue(label="CX13 browser", makerspace=space, client_type="browser",
                                    allowed_origins=["http://testserver"], scopes=["public:read"])
        fetch = lambda path: APIClient().get(path, HTTP_X_CLIENT_ID=client.client_id,
                                             HTTP_ORIGIN="http://testserver")
    response = fetch(BASE)
    assert response.status_code == 200
    if condition in {"minor", "restricted", "suspended"}:
        assert response.json() == {"display_name": "Maker 名", "avatar_url": None}
    else:
        assert response.json() == {
            "display_name": "Maker 名", "avatar_url": None, "handle": "cx13.maker",
            "bio": "" if condition == "no_profile" else "Builds useful things", "projects": [],
            "memberships": [] if space is None else [{
                "slug": space.slug, "name": space.name, "role_title": "Member", "started_on": "2025-01-02"}],
        }
    shared = fetch(SHARED)
    assert shared.status_code == 200
    assert shared.json() == {"kind": "member", "handle": "cx13.maker",
                            "canonical_url": "http://testserver/@cx13.maker", "redirected": False,
                            "content_url": BASE}
    assert AccountProfile.objects.filter(user=person).exists() is (condition != "no_profile")


@pytest.mark.parametrize("path", [BASE, SHARED])
@pytest.mark.parametrize("fence", ["client", "host", "origin"])
def test_missing_and_foreign_target_have_identical_canonical_refusal(person, enforced, path, fence):
    own, _ = add_membership(person)
    other = Makerspace.objects.create(name="Foreign", slug="cx13-other-admission",
                                      frontend_domain="foreign.example.test", frontend_domain_status="verified")
    client, secret = issue(other if fence == "client" else own)
    headers = {"HTTP_HOST": other.frontend_domain} if fence == "host" else (
        {"HTTP_ORIGIN": "https://foreign.example.test"} if fence == "origin" else {})
    hidden = read(client, secret, path, **headers)
    missing = read(client, secret, path.replace("cx13.maker", "missing.maker"), **headers)
    assert hidden.status_code == 404
    assert missing.status_code == 404
    assert hidden.json() == missing.json() == {"detail": "Not found.", "code": "not_found"}


@pytest.mark.parametrize("path", [BASE, SHARED])
def test_credentials_and_scopes_are_still_required(person, enforced, path):
    client, secret = issue(scopes=["public:write"])
    missing = APIClient().get(path)
    denied = read(client, secret, path)
    bad_signature = APIClient().get(path, HTTP_X_CLIENT_ID=client.client_id,
                                    HTTP_X_TIMESTAMP="1", HTTP_X_SIGNATURE="invalid")
    for response in (missing, denied, bad_signature):
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid client signature."}


@pytest.mark.parametrize("suffix", ["activity", "events", "projects", "github"])
def test_enforced_satellites_keep_legacy_consent_gate(person, enforced, suffix):
    space, _ = add_membership(person)
    client, secret = issue(space)
    response = read(client, secret, BASE + suffix)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found.", "code": "not_found"}


@pytest.fixture
def multi_space(person):
    a, _ = add_membership(person, "cx13-a", frontend_domain="a.example.test",
                          frontend_domain_status="verified")
    b, newest = add_membership(person, "cx13-b", frontend_domain="b.example.test",
                               frontend_domain_status="verified")
    newest.activated_at = datetime(2025, 2, 1, 20, 0, tzinfo=dt_timezone.utc)
    newest.save(update_fields=["activated_at"])
    return a, b


def tenant_fetch(space, transport, *, host, origin):
    """Real middleware credentials; never bypass admission with force_authenticate."""
    headers = {"HTTP_HOST": host, "HTTP_ORIGIN": origin}
    if transport == "publishable":
        return lambda path: APIClient().get(path, HTTP_X_PUBLISHABLE_KEY=space.public_api_key, **headers)
    client, secret = ApiClient.issue(
        label="CX13 tenant reader", makerspace=space,
        client_type="browser" if transport == "browser" else "server",
        allowed_origins=[origin], scopes=["public:read"])
    if transport == "signed":
        return lambda path: read(client, secret, path, **headers)
    return lambda path: APIClient().get(path, HTTP_X_CLIENT_ID=client.client_id, **headers)


@pytest.mark.parametrize("transport", ["publishable", "browser", "signed"])
def test_enforced_non_home_tenant_clients_reach_cards_and_shared_handles(multi_space, enforced, transport):
    a, b = multi_space
    fetch = tenant_fetch(a, transport, host=a.frontend_domain, origin="https://a.example.test")
    response = fetch(BASE)
    assert response.status_code == 200
    assert response.json() == {
        "display_name": "Maker 名", "avatar_url": None, "handle": "cx13.maker",
        "bio": "Builds useful things", "projects": [],
        "memberships": [
            {"slug": a.slug, "name": a.name, "role_title": "Member", "started_on": "2025-01-02"},
            {"slug": b.slug, "name": b.name, "role_title": "Member", "started_on": "2025-02-02"},
        ],
    }
    shared = fetch(SHARED)
    assert shared.status_code == 200
    assert shared.json() == {"kind": "member", "handle": "cx13.maker",
                            "canonical_url": "http://testserver/@cx13.maker", "redirected": False,
                            "content_url": BASE}


@pytest.mark.parametrize("path", [BASE, SHARED])
def test_scoped_target_is_a_and_unscoped_target_remains_newest_b(multi_space, path):
    a, b = multi_space
    entry = lookup(resolve(path).view_name, "GET")
    scoped = RequestFactory().get(path, HTTP_HOST=a.frontend_domain, HTTP_ORIGIN="https://a.example.test")
    unscoped = RequestFactory().get(path)
    for request, expected in [(scoped, a), (unscoped, b)]:
        target, resolved = resolve_target(request, entry)
        assert (target.kind, target.pk, resolved, is_global_target(target)) == ("tenant", expected.pk, True, False)
    conflicting = RequestFactory().get(path, HTTP_HOST=b.frontend_domain, HTTP_ORIGIN="https://a.example.test")
    assert resolve_target(conflicting, entry) == (None, False)


@pytest.mark.parametrize("transport", ["publishable", "browser", "signed"])
@pytest.mark.parametrize("path", [BASE, SHARED])
@pytest.mark.parametrize("fence", ["conflicting_scopes", "wrong_client", "unrelated_person", "missing_handle"])
def test_multi_space_admission_keeps_exact_tenant_fences(multi_space, enforced, transport, path, fence):
    a, b = multi_space
    credential_space = b if fence == "wrong_client" else a
    # Both keys trust this origin: wrong-client denial must still enforce target equality.
    if fence == "wrong_client":
        b.cors_allowed_origins = ["https://a.example.test"]
        b.save(update_fields=["cors_allowed_origins"])
    host = b.frontend_domain if fence == "conflicting_scopes" else a.frontend_domain
    if fence == "unrelated_person":
        # Leave only home B: tenant A must not reach this card with any credential.
        MakerspaceMembership.all_tracks.filter(makerspace=a).update(status="revoked")
    if fence == "missing_handle":
        path = path.replace("cx13.maker", "missing.maker")
    response = tenant_fetch(credential_space, transport, host=host, origin="https://a.example.test")(path)
    if transport != "signed":
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid client signature."}
    else:
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found.", "code": "not_found"}


@pytest.mark.parametrize("path", [BASE, SHARED])
@pytest.mark.parametrize("setting", ["public_site_enabled", "enabled_modules"])
def test_nonpublic_scoped_membership_keeps_home_fallback_and_restores(person, multi_space, enforced, path, setting):
    a, b = multi_space
    entry = lookup(resolve(path).view_name, "GET")
    original = getattr(a, setting)
    setattr(a, setting, False if setting == "public_site_enabled" else ["member_accounts"])
    a.save(update_fields=[setting])
    request = RequestFactory().get(path, HTTP_HOST=a.frontend_domain, HTTP_ORIGIN="https://a.example.test")
    target, resolved = resolve_target(request, entry)
    assert (target.kind, target.pk, resolved, is_global_target(target)) == ("tenant", b.pk, True, False)
    fetch = tenant_fetch(a, "publishable", host=a.frontend_domain, origin="https://a.example.test")
    response = fetch(path)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid client signature."}
    setattr(a, setting, original)
    a.save(update_fields=[setting])
    target, resolved = resolve_target(request, entry)
    assert (target.kind, target.pk, resolved, is_global_target(target)) == ("tenant", a.pk, True, False)
    restored = fetch(path)
    assert restored.status_code == 200
    assert MakerspaceMembership.all_tracks.filter(user=person, status="active").count() == 2
