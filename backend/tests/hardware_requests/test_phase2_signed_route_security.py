"""New equipment routes reject real signed clients under widened prefixes (unrun)."""
import hashlib
import hmac
import time
import pytest
from cryptography.fernet import Fernet
from django.urls import resolve
from rest_framework.test import APIClient
from apps.apiclients.models import ApiClient as IntegrationClient
from apps.apiclients.scope_registry import lookup
from tests.return_helpers import make_space

ROUTES = [
    ("POST", "/api/v1/public/demo/requests/contextual", "hardware_requests:contextual-request-self"),
    ("GET", "/api/v1/public/demo/equipment-kits/", "hardware_requests:equipment-kit-public-list"),
    ("GET", "/api/v1/public/demo/equipment-kits/1/", "hardware_requests:equipment-kit-public-detail"),
    ("POST", "/api/v1/admin/makerspace/1/equipment-requests/contextual", "hardware_requests:contextual-request-staff"),
    ("GET", "/api/v1/admin/makerspace/1/equipment-kits", "hardware_requests:equipment-kit-list"),
    ("POST", "/api/v1/admin/makerspace/1/equipment-kits", "hardware_requests:equipment-kit-list"),
    ("GET", "/api/v1/admin/makerspace/1/equipment-kits/1", "hardware_requests:equipment-kit-detail"),
    ("POST", "/api/v1/admin/makerspace/1/equipment-kits/1/versions", "hardware_requests:equipment-kit-version"),
    ("POST", "/api/v1/admin/makerspace/1/equipment-kits/1/publication", "hardware_requests:equipment-kit-publication"),
    ("POST", "/api/v1/admin/makerspace/1/equipment-kits/1/archive", "hardware_requests:equipment-kit-archive"),
    ("GET", "/api/v1/admin/makerspace/1/events/1/equipment-request-products", "event-equipment-request-products"),
    ("GET", "/api/v1/admin/makerspace/1/events/1/equipment-kits", "event-equipment-kits"),
    ("GET", "/api/v1/admin/makerspace/1/spaces/1/equipment-request-products", "booking-equipment-request-products"),
    ("GET", "/api/v1/admin/makerspace/1/spaces/1/equipment-kits", "booking-equipment-kits"),
    ("GET", "/api/v1/admin/makerspace/1/consumables/1/equipment-sources", "admin-consumable-equipment-sources"),
]

@pytest.mark.django_db
@pytest.mark.parametrize("method,path,name", ROUTES)
def test_signed_client_is_denied_for_each_session_route(settings, method, path, name):
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/", "/api/v1/admin/"]
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    maker = make_space("route-security-matrix")
    client, secret = IntegrationClient.issue(label="legacy", scopes=["legacy:v1"], makerspace=maker,
        client_type="server", allowed_origins=["https://integration.example"])
    assert resolve(path).view_name == name
    assert lookup(name, method) is None
    body = b"{}" if method == "POST" else b""
    stamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), b"\n".join([method.encode(), path.encode(), stamp.encode(), body]), hashlib.sha256).hexdigest()
    response = APIClient().generic(method, path, body, content_type="application/json",
        HTTP_X_CLIENT_ID=client.client_id, HTTP_X_TIMESTAMP=stamp,
        HTTP_X_SIGNATURE=signature, HTTP_ORIGIN="https://integration.example")
    assert response.status_code in (401, 403), response.content
