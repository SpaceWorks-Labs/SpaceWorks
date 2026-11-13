"""Native (Android/iOS) contract for the 0.12.0 routes; the apps generate clients from the schema.

Staff routes must resolve their tenant from the path, because a native staff grant must send a
matching X-Makerspace-Id; member routes must sit on the member surface. Operation IDs and enum
names must be explicit, since generated clients break on `_2` suffixes and hashed enum names.
"""
import pytest
from django.test import RequestFactory
from django.urls import resolve
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.authentication import _member_surface_path_allowed
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
from apps.makerspaces.origin_scope_routes import request_route_targets

# Staff routes whose tenant is the path's makerspace_id (no database lookup needed).
NATIVE_STAFF_ROUTES = (
    ("equipment-kit-list", "/api/v1/admin/makerspace/7/equipment-kits"),
    ("equipment-kit-detail", "/api/v1/admin/makerspace/7/equipment-kits/3"),
    ("equipment-kit-version", "/api/v1/admin/makerspace/7/equipment-kits/3/versions"),
    ("contextual-request-staff", "/api/v1/admin/makerspace/7/equipment-requests/contextual"),
    ("event-equipment-request-products", "/api/v1/admin/makerspace/7/events/3/equipment-request-products"),
    ("event-equipment-kits", "/api/v1/admin/makerspace/7/events/3/equipment-kits"),
    ("booking-equipment-request-products", "/api/v1/admin/makerspace/7/spaces/3/equipment-request-products"),
    ("booking-equipment-kits", "/api/v1/admin/makerspace/7/spaces/3/equipment-kits"),
    ("admin-request-event-context", "/api/v1/admin/makerspace/7/requests/3/event-context"),
    ("admin-request-booking-context", "/api/v1/admin/makerspace/7/requests/3/booking-context"),
    ("admin-related-facts-event", "/api/v1/admin/makerspace/7/related-facts/events/3"),
    ("admin-related-facts-booking", "/api/v1/admin/makerspace/7/related-facts/bookings/3"),
    ("admin-event-booking-link", "/api/v1/admin/makerspace/7/events/3/booking-link"),
    ("finance-event-linked", "/api/v1/admin/makerspace/7/finance/events/3/linked"),
    ("admin-loan-repairs", "/api/v1/admin/makerspaces/7/requests/3/repairs"),
)
NATIVE_MEMBER_ROUTES = (
    ("contextual-request-self", "/api/v1/public/demo/requests/contextual"),
    ("equipment-kit-public-list", "/api/v1/public/demo/equipment-kits/"),
    ("equipment-kit-public-detail", "/api/v1/public/demo/equipment-kits/3/"),
)
EXPLICIT_OPERATION_IDS = {
    ("get", "/api/v1/admin/makerspace/{makerspace_id}/equipment-kits"): "api_v1_admin_makerspace_equipment_kits_list",
    ("get", "/api/v1/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}"):
        "api_v1_admin_makerspace_equipment_kit_retrieve",
    ("get", "/api/v1/public/{makerspace_slug}/equipment-kits/"): "api_v1_public_equipment_kits_list",
    ("get", "/api/v1/public/{makerspace_slug}/equipment-kits/{kit_id}/"): "api_v1_public_equipment_kit_retrieve",
    ("post", "/api/v1/notifications/browser-firebase/may-resume"):
        "api_v1_notifications_browser_firebase_may_resume_create",
    ("post", "/api/v1/notifications/browser-firebase/{makerspace_id}/may-resume"):
        "api_v1_notifications_browser_firebase_space_may_resume_create",
}


@pytest.fixture(scope="module")
def document():
    return SchemaGenerator().get_schema(request=None, public=True)


@pytest.mark.parametrize("name,path", NATIVE_STAFF_ROUTES)
def test_staff_route_is_staff_classed_and_resolves_the_native_header_tenant(name, path):
    match = resolve(path)
    assert match.url_name == name
    assert route_class(name) in {DELEGABLE, MEMBERSHIP_ONLY}
    request = RequestFactory().get(path)
    request.resolver_match = match
    assert request_route_targets(request) == (name, {7}, False, True)


@pytest.mark.parametrize("name,path", NATIVE_MEMBER_ROUTES)
def test_member_route_is_on_the_member_surface(name, path):
    assert resolve(path).url_name == name
    assert route_class(name) is None
    assert _member_surface_path_allowed(path)


def test_new_operations_have_explicit_ids(document):
    for (method, path), operation_id in EXPLICIT_OPERATION_IDS.items():
        assert document["paths"][path][method]["operationId"] == operation_id


def test_operation_ids_are_unique(document):
    ids = [op["operationId"] for item in document["paths"].values() for op in item.values()
           if isinstance(op, dict) and "operationId" in op]
    assert len(ids) == len(set(ids))


def test_equipment_kit_enums_have_stable_names(document):
    schemas = document["components"]["schemas"]
    assert schemas["KitLineKindEnum"]["enum"] == ["returnable", "consumable"]
    assert schemas["ContextualRequestOutcomeEnum"]["enum"] == ["request", "consumable_plan"]
    assert "Kind5faEnum" not in schemas and "Kind47fEnum" not in schemas
