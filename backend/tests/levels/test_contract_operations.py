"""Contract level: the generated OpenAPI document and the running API agree, operation by operation.

The existing guard (`apps.openapi_contract`) proves each operation is *documented* completely. These tests
prove the document is *true*: every operation reaches a live view that implements its verb, an operation
documented as needing credentials really refuses an anonymous caller, and error bodies are named components
a generated client can type.
"""
import pytest
from rest_framework.test import APIClient

from tests.levels.schema_tools import live_schema, operations, probe, resolved_url

pytestmark = pytest.mark.django_db

# 400 is deliberately NOT here: DRF checks permissions before validating, so a 400 to an anonymous caller means
# the credential check was skipped. Signature-verified webhooks answer 400/401/403 to an unsigned body.
REFUSED = {401, 403, 404, 405, 410, 415, 429}
SIGNED = ("/webhooks/", "/webhook")
# Ceiling for documented error bodies that are still an inline free-form object instead of a named component.
# Ratchet: lower it when you type some, never raise it.
MAX_INLINE_ERROR_BODIES = 420


def test_the_schema_is_large_enough_to_mean_something():
    assert len(operations()) > 2000


def test_every_operation_reaches_a_live_view_that_implements_its_verb():
    failures = []
    for method, path, operation, item in operations():
        _url, problem = resolved_url(method, path, operation, item)
        if problem:
            failures.append(f"{method.upper()} {path}: {problem}")
    assert not failures, f"{len(failures)} documented operations are not live:\n" + "\n".join(failures[:60])


def test_operations_documented_as_authenticated_refuse_an_anonymous_caller():
    client = APIClient(raise_request_exception=False)
    failures = []
    for method, path, operation, item in operations():
        if {} in operation.get("security", []):
            continue  # documented as open to anonymous callers
        url, problem = resolved_url(method, path, operation, item)
        if problem:
            continue  # reported by the test above
        status = probe(client, method, url).status_code
        accepted = REFUSED | ({400} if any(s in path for s in SIGNED) else set())
        if status not in accepted:
            failures.append(f"{method.upper()} {path}: anonymous got {status}")
    assert not failures, f"{len(failures)} authenticated operations answered an anonymous caller:\n" + "\n".join(failures[:60])


def test_documented_error_bodies_are_typed_components():
    inline = []
    for method, path, operation, _item in operations():
        for code, response in operation["responses"].items():
            if code[:1] not in "45":
                continue
            for media, body in response.get("content", {}).items():
                if media.endswith("json") and "$ref" not in body.get("schema", {}):
                    inline.append(f"{method.upper()} {path} {code}")
    assert len(inline) <= MAX_INLINE_ERROR_BODIES, (
        f"{len(inline)} inline error bodies (ceiling {MAX_INLINE_ERROR_BODIES}); name the new ones:\n" + "\n".join(inline[-30:]))


def test_every_error_component_is_an_object_a_client_can_read():
    components = live_schema()["components"]["schemas"]
    names = {body["schema"]["$ref"].rsplit("/", 1)[1]
             for _m, _p, operation, _i in operations() for code, response in operation["responses"].items()
             if code[:1] in "45" for body in response.get("content", {}).values() if "$ref" in body.get("schema", {})}
    assert names, "no typed error components found"
    not_objects = sorted(n for n in names if components[n].get("type") not in (None, "object") and "properties" not in components[n])
    assert not_objects == []
