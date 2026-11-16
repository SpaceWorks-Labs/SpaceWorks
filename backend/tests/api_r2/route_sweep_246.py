"""Helpers for the decision-246 whole-API route sweep: walk the URLconf and build concrete URLs."""
import re
import uuid

from django.urls import URLPattern, URLResolver, get_resolver

CONVERTER = re.compile(r"<(?:(?P<conv>[a-z]+):)?(?P<name>[a-zA-Z_]+)>")
# "messaging/twilio": provider webhooks are authenticated by the provider's signature, not a session (they answer
# 415 to a JSON probe before any signature check), so an anonymous probe is not a refusal test there.
SKIP_FRAGMENTS = ("public", "webhook", "callback", "oauth", "download", "export", "stream", "docs", "schema",
                  "messaging/twilio")


def _walk(patterns, prefix=""):
    for entry in patterns:
        route = getattr(entry.pattern, "_route", None)
        if route is None:  # re_path: not representable, skip
            continue
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + route)
        elif isinstance(entry, URLPattern):
            yield prefix + route


def space_routes(prefix_filter=("api/v1/",)):
    """Every makerspace-scoped route under api/v1, as a template string."""
    found = set()
    for route in _walk(get_resolver().url_patterns):
        if "<int:makerspace_id>" not in route or not route.startswith(prefix_filter):
            continue
        if any(fragment in route for fragment in SKIP_FRAGMENTS):
            continue
        found.add(route)
    return sorted(found)


def fill(route, makerspace_id):
    def sub(match):
        name, conv = match.group("name"), match.group("conv")
        if name == "makerspace_id":
            return str(makerspace_id)
        if conv == "int":
            return "987654"
        if conv == "uuid":
            return str(uuid.UUID(int=987654))
        return "zz-none"
    return "/" + CONVERTER.sub(sub, route)
