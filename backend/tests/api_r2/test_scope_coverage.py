"""#193: every route is deliberately in or out of API-client reach; area scopes narrow, never widen."""
import pytest

from apps.apiclients import scope_registry
from apps.apiclients.checks import check_scope_registry
from apps.apiclients.scope_registry_areas import AREAS, PEER_AREAS, area_for
from apps.apiclients.scope_registry_coverage import out_of_scope_reason, unclassified_routes
from apps.apiclients.scope_registry_routes import PUBLIC_READ_SCOPES, PUBLIC_WRITE_SCOPES


def test_system_check_passes_when_called_like_django():
    assert check_scope_registry(app_configs=None) == []


def test_no_route_is_unclassified():
    assert unclassified_routes() == []


def test_staff_member_auth_and_release2_staff_routes_are_out():
    for route in ("api/v1/admin/shop/orders/1/ready/", "api/v1/member/shop/orders/1/cancel/",
                  "api/v1/auth/login", "api/v1/admin/makerspace/1/pricing/discounts/1/archive",
                  "api/v1/admin/id-programmes/1/approval", "api/v1/admin/machine-sessions/1/stop",
                  "api/v1/admin/issues/1/start", "control/", "api/v1/oauth/token/"):
        assert out_of_scope_reason(route), route


def test_every_public_entry_has_one_area_and_its_scope():
    public = {k: e for k, e in scope_registry.SCOPE_REGISTRY.items()
              if e.scopes & (PUBLIC_READ_SCOPES | PUBLIC_WRITE_SCOPES)}
    assert public
    for (name, _method), entry in public.items():
        assert entry.area in AREAS and area_for(name) == entry.area
        assert f"public:{entry.area}:{entry.access}" in entry.scopes


def test_area_scope_reaches_only_its_area():
    shop = scope_registry.lookup("public-shop-products", "GET")
    stats = scope_registry.lookup("public-makerspace-stats", "GET")
    assert scope_registry.scope_allows(shop, ["public:shop:read"])
    assert not scope_registry.scope_allows(stats, ["public:shop:read"])
    assert scope_registry.scope_allows(stats, ["public:read"])
    write = scope_registry.lookup("public-shop-orders", "POST")
    assert not scope_registry.scope_allows(write, ["public:shop:read"])


def test_unknown_route_still_denied_before_wildcards():
    assert scope_registry.lookup("admin-api-clients", "GET") is None


def test_area_scopes_are_in_vocabulary_and_tenant_grantable():
    from apps.apiclients.scope_grants import TENANT_GRANTABLE_SCOPES
    assert scope_registry.AREA_SCOPES <= scope_registry.SCOPE_VOCABULARY
    assert scope_registry.AREA_SCOPES <= TENANT_GRANTABLE_SCOPES
    assert {f"public:{a}:read" for a in PEER_AREAS} <= scope_registry.AREA_SCOPES


@pytest.mark.parametrize("name", ["public-shop", "public-donation-page", "public-id-programme", "pricing-quote",
                                  "public-issue-report", "events-programme-public-results",
                                  "public-makerspace-stats"])
def test_release2_public_routes_have_areas(name):
    assert area_for(name) is not None
