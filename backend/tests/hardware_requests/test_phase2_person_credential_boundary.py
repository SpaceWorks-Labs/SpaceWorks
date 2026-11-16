"""Use real PAT and OAuth credentials against the equipment session boundary."""
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.inventory.models_equipment_proposals import EquipmentConsumableUseReceipt
from apps.operations.models import InventoryAdjustment
from tests.api_r2.test_person_credentials import REDIRECT, _bearer, _create, _query, _register
from tests.hardware_requests.test_phase2_signed_route_security import ROUTES
from tests.return_helpers import authenticated_client, make_member, make_product, make_space


SCOPES = ["public:read", "public:write", "staff:read", "staff:write"]


def delegated_credential(kind, actor, space):
    if kind == "pat":
        created = _create(actor, scopes=SCOPES, makerspace=space.pk)
        assert created.status_code == 201, created.content
        return created.json()["token"]
    registered = _register(space, allowed_scopes=SCOPES)
    assert registered.status_code == 201, registered.content
    app = registered.json()
    verifier, query = _query(app, scope=" ".join(SCOPES))
    consent = authenticated_client(actor).post(
        f"/api/v1/auth/oauth/authorize?{query}", {"allow": True}, format="json",
    )
    assert consent.status_code == 200, consent.content
    code = parse_qs(urlsplit(consent.json()["redirect_to"]).query)["code"][0]
    exchanged = APIClient().post("/api/v1/oauth/token/", {
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "client_id": app["client_id"], "client_secret": app["client_secret"], "code_verifier": verifier,
    })
    assert exchanged.status_code == 200, exchanged.content
    return exchanged.json()["access_token"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["pat", "oauth"])
def test_real_delegated_token_keeps_ordinary_use_but_cannot_reach_equipment_sessions(settings, kind):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/"]
    maker = make_space(f"equipment-credential-{kind}")
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"inventory.consumables"})
    maker.save(update_fields=["enabled_features"])
    actor = make_member(f"equipment-{kind}-manager", maker)
    item = make_product(maker, is_consumable=True, available_quantity=10, total_quantity=10)
    token = delegated_credential(kind, actor, maker)
    assert token.startswith("swpat_" if kind == "pat" else "swoa_")
    api = _bearer(token)
    path = f"/api/v1/admin/makerspace/{maker.pk}/consumables/{item.pk}/use"
    normal = api.post(path, {"quantity": 1, "note": "Ordinary use"}, format="json")
    assert normal.status_code == 200, normal.content
    initial = (InventoryAdjustment.objects.count(), AuditLog.objects.count())
    for fields in ({"operation_id": str(uuid4()), "plan_id": 1}, {"plan_id": None}):
        denied = api.post(path, {"quantity": 1, **fields}, format="json")
        assert denied.status_code == 403, denied.content
        assert "requires an account session" in denied.json()["detail"]
    for method, sample, _name in ROUTES:
        endpoint = sample.replace("/demo/", f"/{maker.slug}/").replace("/makerspace/1/", f"/makerspace/{maker.pk}/")
        response = api.generic(method, endpoint, b"{}" if method == "POST" else b"", content_type="application/json")
        assert response.status_code == 401, (method, endpoint, response.content)
    item.refresh_from_db()
    assert item.available_quantity == 9
    assert initial == (InventoryAdjustment.objects.count(), AuditLog.objects.count())
    assert not EquipmentConsumableUseReceipt.objects.filter(makerspace=maker).exists()
