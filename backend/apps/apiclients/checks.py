from django.core.checks import Error, Tags, register

from apps.apiclients.scope_registry import (
    LEGACY_SCOPE,
    SCOPE_REGISTRY,
    SCOPE_VOCABULARY,
    unregistered_protected_routes,
)


@register(Tags.urls)
def check_scope_registry(app_configs=None, **_kwargs):
    errors = []
    used = frozenset(scope for entry in SCOPE_REGISTRY.values() for scope in entry.scopes)
    unknown = used - SCOPE_VOCABULARY
    unused = SCOPE_VOCABULARY - used - {LEGACY_SCOPE}
    if unknown or unused:
        errors.append(Error(
            "API-client scope vocabulary disagrees with the route registry: "
            f"unknown={sorted(unknown)}, unused={sorted(unused)}.",
            hint="Every supported scope must authorize a registered route.",
            id="apiclients.E002",
        ))
    from .scope_registry_coverage import unclassified_routes
    unclassified = unclassified_routes()
    if unclassified:
        errors.append(Error(
            "Routes are neither API-client routes nor deliberately out of scope: "
            + "; ".join(f"/{route} ({name or 'unnamed route'})" for route, name in unclassified),
            hint="Register the route under a protected prefix, or list its prefix in "
                 "apps/apiclients/scope_registry_coverage.py with the credential that serves it.",
            id="apiclients.E003",
        ))
    missing = unregistered_protected_routes()
    if not missing:
        return errors
    labels = [
        f"/{route} [{method or 'unknown method'}] ({view_name or 'unnamed route'})"
        for route, view_name, method in missing
    ]
    return errors + [
        Error(
            "HMAC-protected routes are missing API-client scope registry entries: "
            + "; ".join(labels),
            hint=(
                "Register every route/method before widening "
                "HMAC_PROTECTED_PATH_PREFIXES."
            ),
            id="apiclients.E001",
        )
    ]
