"""Route security inventory for the event booking decision; source tests unrun."""
import pytest
from django.test import RequestFactory
from django.urls import resolve

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.scope_registry import LEGACY_SCOPE, lookup, scope_allows, validate_registry
from apps.makerspaces.origin_scope_routes import request_route_targets

PATH = "/api/v1/admin/makerspace/7/events/11/booking-link"
NAME = "admin-event-booking-link"


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST"])
def test_decision_route_is_session_only_and_maker_origin_scoped(method):
    match = resolve(PATH)
    assert match.url_name == NAME
    assert IsActiveStaff in match.func.view_class.permission_classes
    assert match.func.view_class.authentication_classes == [SpaceWorksJWTAuthentication]
    entry = lookup(NAME, method)
    assert entry is not None and not entry.scopes and not entry.legacy_v1 and not entry.tenant_apps_admitted
    assert not scope_allows(entry, [LEGACY_SCOPE, "public:*", "public:read", "unknown"])
    request = RequestFactory().generic(method, PATH)
    request.resolver_match = match
    assert request_route_targets(request) == (NAME, {7}, False, True)


def test_route_registry_is_consistent():
    validate_registry()


def test_decision_schema_exposes_only_existing_booking_and_jwt():
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator().get_schema(request=None, public=True)
    path = "/api/v1/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link"
    operations = schema["paths"][path]
    for method in ("get", "post"):
        assert {"200", "400", "401", "403", "404", "409", "423"} <= set(operations[method]["responses"])
        assert operations[method]["security"] == [{"jwtAuth": []}]
    fields = schema["components"]["schemas"]["DecisionInput"]["properties"]
    assert "existing_booking_id" in fields and "booking" not in fields
    assert fields["existing_booking_id"]["maximum"] == 9007199254740991
    assert fields["expected_revision"]["maximum"] == 9007199254740991


def test_conflicting_tenant_query_cannot_override_path_scope():
    request = RequestFactory().get(PATH, {"makerspace_id": "8"})
    request.resolver_match = resolve(PATH)
    name, targets, invalid, recognized = request_route_targets(request)
    assert recognized and name == NAME
    assert invalid or targets == {7}
