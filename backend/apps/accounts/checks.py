"""Build guard for the staff surface's explicit authority-source registry."""

from django.core.checks import Error, Tags, register
from django.urls import URLPattern, URLResolver, get_resolver

from .delegated_routes import route_class

# Staff routes are spread across domain apps, including the shared auth surface.
# Non-browser protocols mounted among them must be explicitly excluded by name;
# otherwise even a newly added callback fails closed until it has been reviewed.
STAFF_PREFIXES = (
    "api/v1/admin/", "api/v1/guest-admin/", "api/v1/auth/",
    "api/v1/procurement/", "api/v1/integrations/", "api/v1/notifications/",
)
SHARED_PATHS = {"api/v1/bootstrap", "api/v1/live/"}
NON_STAFF_ROUTES = frozenset({
    "telegram-webhook", "email-bounce-webhook", "whatsapp-meta-webhook",
    "whatsapp-twilio-inbound", "whatsapp-twilio-status",
    "notification-slack-oauth", "notification-slack-inbound",
    "notification-mattermost-oauth", "notification-mattermost-inbound",
    "notification-discord-oauth", "notification-discord-inbound",
    "one-click-unsubscribe", "announcement-feed",
})


def staff_routes(patterns, prefix=""):
    """Walk includes rather than relying on reverse_dict (which drops unnamed URLs)."""
    for pattern in patterns:
        route = prefix + str(pattern.pattern).removeprefix("^").removesuffix("$")
        if isinstance(pattern, URLResolver):
            yield from staff_routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            if pattern.name in NON_STAFF_ROUTES:
                continue
            if route.startswith(STAFF_PREFIXES) or route in SHARED_PATHS:
                yield route, pattern.name


@register(Tags.urls)
def check_delegated_routes(app_configs=None, **kwargs):
    return [Error(
        f"Staff API route /{route} ({name or 'unnamed'}) has no account-surface classification.",
        hint="Classify the URL name in accounts.delegated_routes before exposing it.",
        id="accounts.E001",
    ) for route, name in staff_routes(get_resolver().url_patterns)
        if route_class(name) is None]
