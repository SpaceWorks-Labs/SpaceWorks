"""The public page's live functional projection links to the standalone Inventory owner."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("tenant_domain", [False, True])
@pytest.mark.parametrize("inventory_enabled", [False, True])
def test_functional_inventory_link_uses_standalone_route(monkeypatch, tenant_domain, inventory_enabled):
    from apps.makerspaces import public_page_access, public_page_projection, editions

    monkeypatch.setattr(public_page_projection, "module_enabled", lambda _space, key: key == "public_inventory")
    monkeypatch.setattr(public_page_projection, "feature_enabled", lambda _space, key: key == "loans.enabled")
    monkeypatch.setattr(editions, "public_surface_available", lambda _key: True)
    origin = "https://tenant.example.test" if tenant_domain else "https://platform.example.test"
    monkeypatch.setattr(public_page_access, "canonical_origin", lambda _space: origin)
    space = SimpleNamespace(slug="lab", frontend_domain="tenant.example.test" if tenant_domain else "",
                            frontend_domain_status="verified" if tenant_domain else "unverified",
                            public_inventory_enabled=inventory_enabled)
    expected = [{"family": "inventory", "url": f"{origin}{'' if tenant_domain else '/m/lab'}/inventory"}] if inventory_enabled else []
    assert public_page_projection.functional_links(space) == {"links": expected}
