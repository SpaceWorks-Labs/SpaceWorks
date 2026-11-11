"""#193: the peer (space-to-space) client reads only public catalogue/events/stats; client CRUD is audited."""
import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.apiclients import scope_registry
from apps.apiclients.models import ApiClient
from apps.apiclients.scope_registry_verdicts import peer_may_reach, target_allows
from apps.audit.models import AuditLog
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db
PEER = ["public:catalogue:read", "public:events:read", "public:stats:read"]


@pytest.fixture(autouse=True)
def _key(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()


def _manager(space):
    from tests.fixed_roles.helpers import assign_builtin_roles
    user = make_user(f"mgr-{space.slug}", access_status=User.AccessStatus.ACTIVE, account_kind="staff",
                     staff_makerspace=space)
    assign_builtin_roles(user, space, "space_manager")
    return user


def test_peer_issue_limits_scopes_and_needs_a_space():
    space = make_space("peer-a")
    client, _secret = ApiClient.issue(label="Space B", makerspace=space, client_type="peer",
                                      allowed_origins=["https://b.example"], scopes=PEER)
    assert client.client_type == "peer"
    with pytest.raises(ValidationError):
        ApiClient.issue(label="Wide", makerspace=space, client_type="peer",
                        allowed_origins=["https://b.example"], scopes=["public:read"])
    with pytest.raises(ValidationError):
        ApiClient.issue(label="Global", makerspace=None, client_type="peer",
                        allowed_origins=["https://b.example"], scopes=PEER)


def test_peer_verdict_refuses_other_areas_writes_and_other_spaces():
    space, other = make_space("peer-b"), make_space("peer-c")
    client, _ = ApiClient.issue(label="B", makerspace=space, client_type="peer",
                                allowed_origins=["https://b.example"], scopes=PEER)
    inventory = scope_registry.lookup("public-inventory", "GET")
    shop = scope_registry.lookup("public-shop-products", "GET")
    submit = scope_registry.lookup("hardware_requests:request-submit", "POST")
    assert peer_may_reach(inventory, "GET") and not peer_may_reach(inventory, "POST")
    assert target_allows(inventory, client, space, True)
    assert not target_allows(inventory, client, other, True)
    assert not target_allows(shop, client, space, True)
    assert not target_allows(submit, client, space, True)
    client.scopes = ["public:read"]  # a widened row (edited, restored) still reaches nothing else
    assert not target_allows(shop, client, space, True)


def test_peer_cannot_reach_signed_staff_reads():
    space = make_space("peer-d")
    client, _ = ApiClient.issue(label="B", makerspace=space, client_type="peer",
                                allowed_origins=["https://b.example"], scopes=PEER)
    entry = scope_registry.lookup("integration-event-list", "GET")
    if entry is not None:
        assert not target_allows(entry, client, space, True)


def test_space_manager_creates_a_peer_and_an_area_scoped_server_client():
    space = make_space("crud-a")
    api = authenticated_client(_manager(space))
    peer = api.post(f"/api/v1/admin/makerspace/{space.pk}/api-clients", {
        "label": "Space B", "client_type": "peer", "scopes": PEER, "allowed_origins": ["https://b.example"]},
        format="json")
    assert peer.status_code == 201, peer.content
    assert peer.json()["client_type"] == "peer" and peer.json()["client_secret"]
    wide = api.post(f"/api/v1/admin/makerspace/{space.pk}/api-clients", {
        "label": "Wide peer", "client_type": "peer", "scopes": ["public:read"],
        "allowed_origins": ["https://b.example"]}, format="json")
    assert wide.status_code == 400
    server = api.post(f"/api/v1/admin/makerspace/{space.pk}/api-clients", {
        "label": "ERP", "scopes": ["public:shop:read"], "allowed_origins": ["https://erp.example"]}, format="json")
    assert server.status_code == 201 and server.json()["client_type"] == "server"
    browser = api.post(f"/api/v1/admin/makerspace/{space.pk}/api-clients", {
        "label": "Site", "client_type": "browser", "scopes": ["public:read"],
        "allowed_origins": ["https://site.example"]}, format="json")
    assert browser.status_code == 201 and browser.json()["client_type"] == "server"  # browser stays global-only


def test_revoke_reactivate_rotate_delete_are_audited():
    space = make_space("crud-b")
    api = authenticated_client(_manager(space))
    created = api.post(f"/api/v1/admin/makerspace/{space.pk}/api-clients", {
        "label": "ERP", "scopes": ["public:read"], "allowed_origins": ["https://erp.example"]}, format="json").json()
    pk = created["id"]
    assert api.patch(f"/api/v1/admin/api-clients/{pk}", {"is_active": False}, format="json").status_code == 200
    assert api.patch(f"/api/v1/admin/api-clients/{pk}", {"is_active": True}, format="json").status_code == 200
    assert api.post(f"/api/v1/admin/api-clients/{pk}/rotate-secret", format="json").status_code == 200
    assert api.delete(f"/api/v1/admin/api-clients/{pk}").status_code == 204
    actions = set(AuditLog.objects.filter(target_id=str(pk)).values_list("action", flat=True))
    assert {"api_client.created", "api_client.revoked", "api_client.reactivated", "api_client.secret_rotated",
            "api_client.deleted"} <= actions


def test_management_views_are_rate_limited():
    from apps.admin_api import api_client_scope_views, api_client_views
    for view in (api_client_views.ApiClientListCreateView, api_client_views.ApiClientDetailView,
                 api_client_views.ApiClientRotateSecretView, api_client_scope_views.ApiClientScopeCatalogView):
        assert view.throttle_scope == "api_client_manage" and view.throttle_classes


def test_scope_catalog_marks_client_types():
    space = make_space("crud-c")
    rows = authenticated_client(_manager(space)).get(
        f"/api/v1/admin/makerspace/{space.pk}/api-client-scopes?page_size=200").json()["results"]
    by_value = {row["value"]: row for row in rows}
    assert "peer" in by_value["public:catalogue:read"]["client_types"]
    assert "peer" not in by_value["public:read"]["client_types"]


def test_peer_signed_request_without_origin_is_accepted_by_origin_gate():
    from apps.inventory.middleware_hmac import FrontendHMACMiddleware
    space = make_space("peer-e")
    client, _ = ApiClient.issue(label="B", makerspace=space, client_type="peer",
                                allowed_origins=["https://b.example"], scopes=PEER)
    request = APIRequestFactory().get(f"/api/v1/public/{space.slug}/stats/")
    assert FrontendHMACMiddleware(lambda r: None)._origin_ok(request, client)
