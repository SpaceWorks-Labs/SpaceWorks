"""Real signed-client regression source; unrun until isolated admission."""
import hashlib
import hmac
import json
import time
from unittest.mock import Mock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from apps.audit.models import AuditLog
from apps.apiclients.models import ApiClient as IntegrationClient
from apps.apiclients import scope_registry
from apps.inventory import equipment_use_service
from apps.inventory.models_equipment_proposals import EquipmentConsumableUseReceipt
from apps.operations.models import InventoryAdjustment
from tests.return_helpers import authenticated_client, make_member, make_product, make_space


@pytest.fixture
def world(settings, monkeypatch):
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/admin/"]
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    space = make_space("linked-signed-client")
    space.enabled_features = sorted(set(space.enabled_features or []) | {"inventory.consumables"})
    space.save(update_fields=["enabled_features"])
    actor = make_member("signed-client-manager", space)
    product = make_product(space, is_consumable=True, available_quantity=10, total_quantity=10)
    signed, secret = IntegrationClient.issue(label="legacy", scopes=["legacy:v1"], makerspace=space,
        client_type="server", allowed_origins=["https://integration.example"])
    # Existing admin route is outside the default protected prefixes. Model a deployment
    # that explicitly admits the existing legacy operation after widening its prefix;
    # HMAC validation, timestamp, body and origin still run through real middleware.
    original = scope_registry.lookup
    entry = scope_registry.ScopeRegistryEntry(frozenset({"legacy:v1"}), scope_registry.TARGET_GLOBAL,
        legacy_v1=True, tenant_apps_admitted=True)  # a tenant-bound client may reach a global route only when admitted
    monkeypatch.setattr(scope_registry, "lookup", lambda name, method: entry
        if name == "admin-consumable-use" and method == "POST" else original(name, method))
    return space, actor, product, signed, secret


def signed_post(actor, signed, secret, path, payload, origin="https://integration.example"):
    body = json.dumps(payload, separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), b"\n".join([b"POST", path.encode(), stamp.encode(), body]), hashlib.sha256).hexdigest()
    return authenticated_client(actor).generic("POST", path, body, content_type="application/json",
        HTTP_X_CLIENT_ID=signed.client_id, HTTP_X_TIMESTAMP=stamp,
        HTTP_X_SIGNATURE=signature, HTTP_ORIGIN=origin)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("extra", [
    {"operation_id": str(uuid4()), "plan_id": 1}, {"plan_id": None},
    {"operation_id": None, "plan_id": None, "unexpected": "x"},
    {"operation_id": "bad", "allocation_id": "bad"},
])
def test_signed_linked_fields_refused_before_any_side_effect(world, monkeypatch, extra):
    space, actor, product, signed, secret = world
    key = Mock(side_effect=AssertionError("key preparation"))
    source = Mock(side_effect=AssertionError("source lookup"))
    monkeypatch.setattr(equipment_use_service, "prepare_tenant_key", key)
    monkeypatch.setattr(equipment_use_service, "_preflight_source", source)
    path = f"/api/v1/admin/makerspace/{space.pk}/consumables/{product.pk}/use"
    before = InventoryAdjustment.objects.count()
    audit_before = AuditLog.objects.count()
    response = signed_post(actor, signed, secret, path, {"quantity": 1, **extra})
    assert response.status_code == 403, response.content
    product.refresh_from_db()
    assert product.available_quantity == 10
    assert InventoryAdjustment.objects.count() == before
    assert AuditLog.objects.count() == audit_before
    assert not EquipmentConsumableUseReceipt.objects.filter(makerspace=space).exists()
    key.assert_not_called(); source.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_signed_legacy_use_still_consumes(world):
    space, actor, product, signed, secret = world
    path = f"/api/v1/admin/makerspace/{space.pk}/consumables/{product.pk}/use"
    response = signed_post(actor, signed, secret, path, {"quantity": 1, "note": "legacy"})
    assert response.status_code == 200, response.content
    product.refresh_from_db()
    assert product.available_quantity == 9


@pytest.mark.django_db(transaction=True)
def test_session_null_source_is_not_legacy_use(world, settings):
    space, actor, product, _signed, _secret = world
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = []
    path = f"/api/v1/admin/makerspace/{space.pk}/consumables/{product.pk}/use"
    response = authenticated_client(actor).post(path, {"quantity": 1, "plan_id": None}, format="json")
    assert response.status_code == 400, response.content
    product.refresh_from_db()
    assert product.available_quantity == 10


@pytest.mark.django_db(transaction=True)
def test_wrong_signed_origin_and_foreign_tenant_do_not_consume(world):
    space, actor, product, signed, secret = world
    path = f"/api/v1/admin/makerspace/{space.pk}/consumables/{product.pk}/use"
    response = signed_post(actor, signed, secret, path, {"quantity": 1}, origin="https://foreign.example")
    assert response.status_code in (401, 403), response.content
    foreign = make_space("linked-foreign-tenant")
    foreign.enabled_features = sorted(set(foreign.enabled_features or []) | {"inventory.consumables"})
    foreign.save(update_fields=["enabled_features"])
    other = make_product(foreign, is_consumable=True, available_quantity=10, total_quantity=10)
    foreign_path = f"/api/v1/admin/makerspace/{foreign.pk}/consumables/{other.pk}/use"
    response = signed_post(actor, signed, secret, foreign_path, {"quantity": 1})
    assert response.status_code in (403, 404), response.content
    product.refresh_from_db(); other.refresh_from_db()
    assert product.available_quantity == other.available_quantity == 10
