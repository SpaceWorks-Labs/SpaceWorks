"""The new route graph is admitted explicitly before any handler runs."""

from uuid import uuid4

import pytest
from django.urls import resolve, reverse

from apps.accounts.claim_route_types import AnonymousRead, Refused
from apps.accounts.claim_routes import policy_for
from apps.accounts.claim_routes_public_pages import (
    MAKERSPACE_PAGE_EDITORS, ORGANIZATION_PAGE_EDITORS, PUBLIC_PAGE_CLAIM_ROUTES,
)
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
from apps.apiclients.scope_registry import lookup, validate_registry
from apps.apiclients.scope_registry_routes import (
    PUBLIC_READ, TARGET_GLOBAL, TARGET_PUBLIC_HANDLE, TARGET_TENANT_SLUG, TARGET_TENANT_TOKEN,
)


@pytest.mark.parametrize("name,kwargs,mode", [
    ("public-page-handle", {"handle": "our.lab"}, TARGET_PUBLIC_HANDLE),
    ("public-makerspace-page", {"makerspace_slug": "lab"}, TARGET_TENANT_SLUG),
    ("public-makerspace-page-asset", {"makerspace_slug": "lab", "asset_id": 1}, TARGET_TENANT_SLUG),
    ("public-organization-page", {"slug": "org"}, TARGET_GLOBAL),
    ("public-organization-page-asset", {"slug": "org", "asset_id": 1}, TARGET_GLOBAL),
    ("public-organization-makerspaces", {"slug": "org"}, TARGET_GLOBAL),
    ("public-event-code", {"public_token": uuid4()}, TARGET_TENANT_TOKEN),
])
def test_public_routes_have_exact_safe_claim_and_hmac_admission(name, kwargs, mode):
    path = reverse(name, kwargs=kwargs)
    assert path.startswith("/api/v1/public/") and resolve(path).url_name == name
    for method in ("GET", "HEAD"):
        entry = lookup(name, method)
        assert entry.target_mode == mode and PUBLIC_READ in entry.scopes
        assert entry.legacy_v1 is False
        assert isinstance(policy_for(name, method), AnonymousRead)
    assert isinstance(policy_for(name, "OPTIONS"), AnonymousRead)
    assert lookup(name, "POST") is None


def test_editor_paths_never_grant_claim_or_client_authority():
    for names, expected in ((MAKERSPACE_PAGE_EDITORS, MEMBERSHIP_ONLY), (ORGANIZATION_PAGE_EDITORS, DELEGABLE)):
        for name in names:
            kwargs = {"pk": 1, **({"asset_id": 2} if name.endswith("-asset") else {})}
            assert reverse(name, kwargs=kwargs).startswith("/api/v1/admin/")
            assert route_class(name) == expected
            for method in ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"):
                assert isinstance(policy_for(name, method), Refused)
                assert lookup(name, method) is None


def test_existing_member_share_and_new_share_routes_are_distinct():
    assert reverse("public-page-share", kwargs={"handle": "our.lab"}) == "/share/pages/our.lab/"
    assert resolve(f"/share/e/{uuid4()}/").url_name == "public-event-code-share"


def test_entire_route_scope_and_claim_matrices_have_no_drift():
    from apps.accounts.claim_route_guard import validate_claim_route_matrix
    from apps.accounts.checks import check_delegated_routes
    assert validate_registry() == ([], [])
    assert validate_claim_route_matrix()
    assert check_delegated_routes() == []
    assert len(PUBLIC_PAGE_CLAIM_ROUTES) == 24  # 7ade2c51 (L1) added public-event-short-code x3 methods


def test_events_tombstone_does_not_import_short_code_urls(monkeypatch):
    import config.urls
    monkeypatch.setattr(config.urls, "runtime_active", lambda app: app != "events")
    assert config.urls.separable("events", "api/v1/", "apps.events.urls_public_codes") == []
