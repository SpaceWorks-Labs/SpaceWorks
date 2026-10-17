"""Build guard for the staff surface's explicit authority-source registry."""

from django.core.checks import Error, Tags, register
from django.urls import URLPattern, URLResolver, get_resolver

from .delegated_routes import route_class
from .route_exemptions import NON_STAFF_ROUTES as NON_STAFF_ROUTES, route_exemption

# Staff routes are spread across domain apps, including the shared auth surface.
# Non-browser protocols mounted among them must be explicitly excluded by name;
# otherwise even a newly added callback fails closed until it has been reviewed.


def all_routes(patterns, prefix=""):
    """Walk includes rather than relying on reverse_dict (which drops unnamed URLs)."""
    for pattern in patterns:
        route = prefix + str(pattern.pattern).removeprefix("^").removesuffix("$")
        if isinstance(pattern, URLResolver):
            yield from all_routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield route, pattern.name


def staff_routes(patterns, prefix=""):
    for route, name in all_routes(patterns, prefix):
        if not route_exemption(route, name):
            yield route, name


@register(Tags.urls)
def check_delegated_routes(app_configs=None, **kwargs):
    return [Error(
        f"Staff API route /{route} ({name or 'unnamed'}) has no account-surface classification.",
        hint="Classify the URL name in accounts.delegated_routes before exposing it.",
        id="accounts.E001",
    ) for route, name in staff_routes(get_resolver().url_patterns)
        if route_class(name) is None]
