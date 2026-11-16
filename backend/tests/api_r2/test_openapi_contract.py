"""#193: the OpenAPI contract guard finds nothing on the real schema, and catches each gap kind."""
import pytest
from django.core.management import call_command
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator

from apps.openapi_contract.check import (
    component_collisions, contract_failures, is_untyped, live_view_keys, stale_entries,
)
from apps.openapi_contract.tags import group_for


@pytest.fixture(scope="module")
def document():
    GENERATOR_STATS.reset()
    return SchemaGenerator().get_schema(request=None, public=True)


def test_every_operation_is_complete(document):
    assert contract_failures(document) == []


def test_no_component_collisions(document):
    assert component_collisions() == []


def test_no_stale_exception_entries():
    assert stale_entries(live_view_keys()) == []


def test_every_tag_has_a_group(document):
    tags = {t for item in document["paths"].values() for op in item.values() if isinstance(op, dict)
            for t in op.get("tags", ())}
    assert sorted(t for t in tags if group_for(t) is None) == []
    grouped = {t for g in document["x-tagGroups"] for t in g["tags"]}
    assert tags <= grouped


def test_public_routes_offer_client_credentials(document):
    security = document["paths"]["/api/v1/public/{makerspace_slug}/stats/"]["get"]["security"]
    assert {"ServerHMAC": []} in security and {} in security
    assert set(document["components"]["securitySchemes"]) >= {"ServerHMAC", "BrowserClient", "PublishableKey",
                                                             "jwtAuth", "personalAccessToken", "oauth2"}


def test_servers_are_same_origin(document):
    assert document["servers"] == [{"url": "/", "description": "This deployment (same origin as these docs)"}]


def _op(**extra):
    op = {"tags": ["Admin events"], "security": [{}], "responses": {
        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/X"}}}},
        "404": {"description": "x"}}}
    op.update(extra)
    return op


@pytest.mark.parametrize("operation,method,problem", [
    (_op(tags=["api"]), "get", "no area tag"),
    (_op(security=None), "get", "no security requirement"),
    (_op(responses={"200": {"content": {"application/json": {"schema": {"type": "integer"}}}}}), "get",
     "no error responses"),
    (_op(), "post", "write without a request body (or an x-request-body: none entry)"),
    (_op(requestBody={"content": {"application/json": {"schema": {"type": "object"}}}}), "post",
     "request body is untyped"),
    (_op(responses={"200": {"content": {"application/json": {"schema": {}}}}, "400": {}}), "get",
     "200 response body is untyped"),
    (_op(responses={"200": {"description": "ok"}, "400": {}}), "get", "200 response has no body schema"),
])
def test_guard_catches_each_gap(operation, method, problem):
    doc = {"paths": {"/x": {method: operation}}, "components": {"schemas": {"X": {"properties": {"a": {}}}}}}
    assert problem in [p for _m, _p, p in contract_failures(doc)]


def test_marks_excuse_deliberate_exceptions():
    doc = {"paths": {"/x": {"post": _op(**{"x-request-body": "none"})}}, "components": {"schemas": {"X": {"properties": {"a": {}}}}}}
    assert contract_failures(doc) == []
    assert is_untyped({"type": "object", "additionalProperties": {}}, {})
    assert not is_untyped({"type": "object", "additionalProperties": {"type": "string"}}, {})


def test_management_command_passes():
    call_command("openapi_contract_check")
