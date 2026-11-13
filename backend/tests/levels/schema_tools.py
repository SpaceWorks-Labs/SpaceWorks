"""TEST-LEVELS helpers: the live OpenAPI document, concrete URLs from it, and a response validator.

Everything is derived from the generated schema (drf-spectacular on the live URLconf), never from a
hand-kept list, so a new route is exercised by the contract tests the day it is added.
"""
import re
import uuid
from functools import lru_cache

from django.core.cache import cache
from django.db import transaction
from django.urls import Resolver404, resolve
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator

METHODS = ("get", "post", "put", "patch", "delete")
WRITES = ("post", "put", "patch")
_PARAM = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=1)
def live_schema():
    GENERATOR_STATS.reset()
    return SchemaGenerator().get_schema(request=None, public=True)


def operations():
    """[(method, path, operation, path_item)] for every documented operation."""
    return [(m, p, item[m], item) for p, item in sorted(live_schema()["paths"].items()) for m in METHODS if m in item]


def _path_params(operation, item):
    found = {}
    for spec in list(item.get("parameters", [])) + list(operation.get("parameters", [])):
        if spec.get("in") == "path":
            found[spec["name"]] = spec.get("schema", {})
    return found


def url_candidates(path, operation, item):
    """Concrete URLs for a template, most likely first: ints are 987654, strings a slug-safe word, then a digit."""
    params = _path_params(operation, item)

    def build(string_value):
        def sub(match):
            schema = params.get(match.group(1), {})
            if schema.get("enum"):
                return str(schema["enum"][0])
            if schema.get("format") == "uuid":
                return str(uuid.UUID(int=987654))
            if schema.get("type") == "integer":
                return "987654"
            return string_value
        return _PARAM.sub(sub, path)

    return [build("zznone"), build("987654")]


def _allowed_methods(callback):
    actions = getattr(callback, "actions", None)
    if actions:
        return {m.upper() for m in actions}
    cls = getattr(callback, "cls", None)
    if cls is None:
        return None  # a plain Django view: cannot be judged
    return {m.upper() for m in getattr(cls, "http_method_names", ()) if hasattr(cls, m)}


def resolved_url(method, path, operation, item):
    """(url, problem): the first candidate URL the URLconf resolves, or why none does."""
    for url in url_candidates(path, operation, item):
        try:
            match = resolve(url)
        except Resolver404:
            continue
        allowed = _allowed_methods(match.func)
        if allowed is not None and method.upper() not in allowed:
            return url, f"view {match.func.__module__} does not implement {method.upper()}"
        return url, None
    return None, "no URL pattern resolves it"


class _Discard(Exception):
    pass


def probe(client, method, url):
    """One request inside a savepoint that is always rolled back; a 5xx is returned, not raised."""
    cache.clear()
    try:
        with transaction.atomic():
            if method.lower() in WRITES:
                response = client.generic(method.upper(), url, b"{}", content_type="application/json")
            else:
                response = getattr(client, method.lower())(url)
            raise _Discard(response)
    except _Discard as done:
        return done.args[0]


# --- response validation against the documented schema ------------------------------------------------


def _inline(node, components, seen=()):
    """Replace $refs by their component and turn OpenAPI 3.0 `nullable` into JSON Schema."""
    if isinstance(node, list):
        return [_inline(item, components, seen) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[1]
        return {} if name in seen else _inline(components[name], components, seen + (name,))
    out = {key: _inline(value, components, seen) for key, value in node.items() if key != "nullable"}
    if node.get("nullable"):
        if isinstance(out.get("enum"), list) and None not in out["enum"]:
            out["enum"] = [*out["enum"], None]
        out = {"anyOf": [out, {"type": "null"}]}
    return out


def response_problems(method, path, status, payload):
    """Why `payload` (a decoded JSON body) breaks the contract for (method, path, status); [] when it conforms."""
    from jsonschema import Draft7Validator

    schema = live_schema()
    operation = schema["paths"][path][method.lower()]
    documented = operation["responses"].get(str(status))
    if documented is None:
        return [f"status {status} is not documented (documented: {sorted(operation['responses'])})"]
    body = documented.get("content", {}).get("application/json")
    if body is None:
        return []
    validator = Draft7Validator(_inline(body["schema"], schema["components"]["schemas"]))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:160]}"
            for e in sorted(validator.iter_errors(payload), key=lambda e: list(map(str, e.absolute_path)))][:6]
