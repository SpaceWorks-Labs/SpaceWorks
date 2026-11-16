"""Context route inventories and schema; run in the admitted isolated suite."""
import pytest
from django.test import RequestFactory
from django.urls import resolve
from drf_spectacular.generators import SchemaGenerator
from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.scope_registry import LEGACY_SCOPE, lookup, scope_allows, validate_registry
from apps.makerspaces.origin_scope_routes import request_route_targets

CASES = (
    ("admin-request-event-context", "/api/v1/admin/makerspace/7/requests/11/event-context"),
    ("admin-direct-loan-event-context", "/api/v1/admin/makerspace/7/direct-loans/11/event-context"),
    ("admin-request-booking-context", "/api/v1/admin/makerspace/7/requests/11/booking-context"),
    ("admin-direct-loan-booking-context", "/api/v1/admin/makerspace/7/direct-loans/11/booking-context"),
)
METHODS = ("GET", "HEAD", "PUT", "DELETE")


@pytest.mark.parametrize("name,path", CASES)
@pytest.mark.parametrize("method", METHODS)
def test_each_live_route_is_session_only_and_origin_scoped(name, path, method):
    match = resolve(path)
    assert match.url_name == name
    assert IsActiveStaff in match.func.view_class.permission_classes
    entry = lookup(name, method)
    assert entry is not None and not entry.scopes and not entry.legacy_v1 and not entry.tenant_apps_admitted
    assert not scope_allows(entry, [LEGACY_SCOPE, "public:*", "public:read", "not-a-real-scope"])
    request = RequestFactory().generic(method, path)
    request.resolver_match = match
    observed_name, targets, invalid, recognized = request_route_targets(request)
    assert (observed_name, targets, invalid, recognized) == (name, {7}, False, True)


@pytest.mark.parametrize("name,path", CASES)
def test_conflicting_tenant_hint_cannot_override_path(name, path):
    request = RequestFactory().get(path, {"makerspace_id": "8"})
    request.resolver_match = resolve(path)
    observed_name, targets, invalid, recognized = request_route_targets(request)
    assert observed_name == name and targets == {7, 8} and invalid and recognized


def test_context_inventory_has_no_missing_or_stale_methods():
    stale, missing = validate_registry()
    names = {name for name, _ in CASES}
    assert not [item for item in stale if item[0] in names]
    assert not [item for item in missing if item[0] in names]
    assert lookup("admin-unregistered-context-route", "GET") is None


def test_context_openapi_has_four_paths_and_typed_methods():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    for name, path in CASES:
        path = path.replace("/7/", "/{makerspace_id}/").replace("/11/", "/{request_id}/" if "direct-loan" not in name else "/{loan_id}/")
        operations = schema["paths"][path]
        for method in ("get", "put", "delete"):
            assert method in operations
            assert {"200", "400", "401", "403", "404", "409", "503"} <= set(operations[method]["responses"])
        assert "requestBody" in operations["put"] and "requestBody" in operations["delete"]
        query_names = {item["name"] for item in operations["get"].get("parameters", []) if item["in"] == "query"}
        assert ("intended_event_id" if "event" in name else "intended_booking_id") in query_names
    components = schema["components"]["schemas"]
    # The two same-named ContextCAS serializers are disambiguated in openapi_contract.component_names.
    for component in ("EventContextPut", "BookingContextPut", "EventLoanContextCAS", "BookingLoanContextCAS"):
        properties = components[component]["properties"]
        assert properties["expected_revision"]["type"] == "integer"
        assert properties["expected_revision"]["maximum"] == 9007199254740991
        assert properties["expected_generation"]["format"] == "uuid"


def test_registered_url_system_check_accepts_route_inventory():
    from apps.apiclients.checks import check_scope_registry
    assert check_scope_registry() == []
