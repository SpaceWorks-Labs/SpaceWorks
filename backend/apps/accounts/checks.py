"""Build guard for the staff surface's explicit authority-source registry."""

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.db import connections
from django.db.utils import OperationalError, ProgrammingError
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


@register(Tags.security)
def check_development_attestation(app_configs=None, **kwargs):
    if settings.DEVICE_ATTESTATION_DEV_INSECURE and not settings.DEBUG:
        return [Error(
            "Development-insecure device attestation requires DEBUG=True.",
            hint="Disable DEVICE_ATTESTATION_DEV_INSECURE before production use.",
            id="accounts.E002",
        )]
    return []


@register(Tags.security)
def check_proxy_topology(app_configs=None, **kwargs):
    """accounts.W002: a managed proxy deployment with no trusted proxy hop resolves every
    client to the proxy, so throttles, axes and the automatic IP block all see one address."""
    if settings.BEHIND_TRUSTED_PROXY and not settings.TRUSTED_PROXY_COUNT:
        return [Warning(
            "BEHIND_TRUSTED_PROXY is on but TRUSTED_PROXY_COUNT is 0.",
            hint="Set TRUSTED_PROXY_COUNT to the number of proxies in front of the backend.",
            id="accounts.W002",
        )]
    return []


@register(Tags.database)
def check_legacy_native_identities(app_configs=None, databases=None, **kwargs):
    from apps.accounts.native_app_identity import eligible_registrations

    warnings = []
    for alias in databases or ["default"]:
        try:
            connection = connections[alias]
            table = "accounts_nativeappregistration"
            if table not in connection.introspection.table_names():
                continue
            with connection.cursor() as cursor:
                columns = {column.name for column in connection.introspection.get_table_description(cursor, table)}
            if "signing_identities" not in columns:
                continue  # The check also runs before migrate on existing installations.
            rows = list(eligible_registrations().using(alias).filter(signing_identities=[])
                        .values_list("pk", "app_id", "environment"))
        except (OperationalError, ProgrammingError):
            continue
        if rows:
            labels = ", ".join(f"#{pk} {app_id} ({environment})" for pk, app_id, environment in rows)
            warnings.append(Warning(
                f"Native registrations have no stored signing identities: {labels}",
                hint="Enter distribution signer digests or the App ID Prefix in /control/; legacy env fallback is temporary.",
                id="accounts.W001",
            ))
    return warnings


@register(Tags.models)
def check_merge_registry(app_configs=None, **kwargs):
    """accounts.E003: every reference to accounts.User has an account-merge disposition."""
    from .merge_registry import problems

    hints = {
        "unclassified_relations": "Classify it in an accounts/merge_registry_rows_*.py fragment.",
        "unclassified_columns": "List the integer user-id column in a merge registry fragment.",
        "stale_relations": "Remove the row: the relation no longer exists.",
        "stale_columns": "Remove the row: the column no longer exists.",
    }
    return [Error(
        f"Account-merge registry: {kind.replace('_', ' ')} {label}.{name}.",
        hint=hints[kind], id="accounts.E003",
    ) for kind, entries in problems().items() for label, name in entries]
