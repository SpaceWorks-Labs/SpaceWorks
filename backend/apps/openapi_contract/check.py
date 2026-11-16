"""The OpenAPI completeness guard: every operation states its whole contract.

`contract_failures(schema)` returns `(method, path, problem)` for each operation that is
missing a tag (or still has drf-spectacular's path-derived "api"), a security requirement,
an error response, a success response, a typed success body, or a request body on a write;
or that carries an untyped body without a FREE_FORM entry saying whose shape it is.
`stale_entries(view_keys)` reports exception entries no live view uses, and
`component_collisions()` the serializers drf-spectacular had to merge under one component
name -- every operation using the loser silently documents the winner's shape.
"""
from .registry import registered_keys
from .tags import group_for

WRITE_METHODS = ("post", "put", "patch")
METHODS = ("get", "post", "put", "patch", "delete")
_NO_BODY_CODES = {"204", "205", "304"}


def _resolve(schema, document):
    ref = schema.get("$ref", "")
    if ref.startswith("#/components/schemas/"):
        return document.get("components", {}).get("schemas", {}).get(ref.rsplit("/", 1)[1], {})
    return schema


def is_untyped(schema, document):
    """True for a body that says nothing about its shape (drf-spectacular's AnyValue/object)."""
    if not isinstance(schema, dict):
        return True
    schema = _resolve(schema, document)
    if any(key in schema for key in ("properties", "items", "oneOf", "anyOf", "allOf", "enum", "$ref")):
        return False
    if schema.get("type") not in (None, "object"):
        return False
    extra = schema.get("additionalProperties")
    return not (isinstance(extra, dict) and extra)


def _bodies(container):
    return [(media, body.get("schema", {})) for media, body in (container or {}).get("content", {}).items()]


def _operation_failures(method, operation, document):
    free = operation.get("x-free-form", {})
    tags = operation.get("tags") or []
    problems = []
    if not tags or tags == ["api"]:
        problems.append("no area tag")
    problems += [f"tag {tag!r} is in no tag group" for tag in tags if group_for(tag) is None]
    if not operation.get("security"):
        problems.append("no security requirement")
    responses = operation.get("responses", {})
    if not any(code[:1] in "45" for code in responses):
        problems.append("no error responses")
    success = [code for code in responses if code[:1] in "23"]
    if not success:
        problems.append("no success response")
    for code in success:
        bodies = _bodies(responses[code])
        if not bodies and code[:1] == "2" and code not in _NO_BODY_CODES \
                and operation.get("x-response-body") != "none":
            problems.append(f"{code} response has no body schema")
        if any(is_untyped(schema, document) for media, schema in bodies
               if media.endswith("json")) and "response" not in free:
            problems.append(f"{code} response body is untyped")
    request = operation.get("requestBody")
    if method in WRITE_METHODS and not request and operation.get("x-request-body") != "none":
        problems.append("write without a request body (or an x-request-body: none entry)")
    if request and operation.get("x-request-body") == "none":
        problems.append("listed as bodyless but documents a request body")
    if request and "request" not in free and any(
            is_untyped(schema, document) for media, schema in _bodies(request)):
        problems.append("request body is untyped")
    return problems


def contract_failures(document):
    failures = []
    for path, item in sorted(document.get("paths", {}).items()):
        for method in METHODS:
            if method in item:
                failures += [(method.upper(), path, problem)
                             for problem in _operation_failures(method, item[method], document)]
    return failures


def stale_entries(live_view_keys):
    return sorted(registered_keys() - frozenset(live_view_keys))


def live_view_keys():
    """(module.Class, METHOD) for every endpoint drf-spectacular documents."""
    from drf_spectacular.generators import EndpointEnumerator
    keys = set()
    for _path, _regex, method, callback in EndpointEnumerator().get_api_endpoints():
        cls = getattr(callback, "cls", None)
        if cls is not None:
            keys.add((f"{cls.__module__}.{cls.__qualname__}", method.upper()))
    return keys


def component_collisions():
    """Distinct serializers that drf-spectacular emitted under one component name.

    Call after generating a schema: spectacular reports a name clash only as a warning,
    yet the second serializer's operations then point at the first one's component.
    """
    from drf_spectacular.drainage import GENERATOR_STATS
    return sorted({message.split("Encountered 2 components with identical names ", 1)[1].split(" and ", 1)[0]
                   for message in GENERATOR_STATS._warn_cache
                   if "Encountered 2 components with identical names" in message})
