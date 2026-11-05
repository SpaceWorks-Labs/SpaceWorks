"""Every URL route is deliberately IN or OUT of API-client reach (#193).

IN: a route under an HMAC-protected prefix (`/api/public/`, `/api/v1/public/`, the signed
integration reads) must have a scope-registry entry -- `apiclients.E001` already refuses
startup otherwise. OUT: every other route is listed here by prefix with the credential
that DOES authenticate it, so a new surface outside the public prefixes is a choice, not
an accident. `apiclients.E003` reports a route that is neither.

An API client's signature is only ever checked on the IN prefixes, so nothing below is
reachable with a client credential, whatever scopes it holds; widening the protected
prefixes onto one of them would need registry entries first (E001).
"""

OUT_OF_SCOPE = (
    ("api/v1/admin/", "Staff console: a person's bearer token, a staff role in the space, staff MFA."),
    ("api/v1/procurement/", "Staff console (the To-Buy list): person token and staff role."),
    ("api/v1/guest-admin/", "Handover desk: person token and a handout role."),
    ("api/v1/member/", "Member surface: the signed-in person acting on their own records."),
    ("api/v1/me", "The signed-in person's own account."),
    ("api/v1/memberships", "Membership joins and renewals by the signed-in person."),
    ("api/v1/auth/", "Sign-in, MFA, passkeys and account recovery: never an API-client surface."),
    ("api/v1/notifications/", "A person's inbox and preferences; unsubscribe links are bearer tokens."),
    ("api/v1/live", "Live updates for a signed-in console session."),
    ("api/v1/bootstrap", "The SPA's boot payload."),
    ("api/v1/config", "The SPA's runtime configuration."),
    ("api/v1/device/", "Enrolled devices: their own Ed25519 request signature."),
    ("api/v1/kiosk-stations/", "Kiosk stations: the station cookie."),
    ("api/v1/event-checkin-stations/", "Event check-in stations: the station cookie."),
    ("api/v1/integrations/", "Provider webhooks (their own signatures) and staff integration settings."),
    ("api/v1/webhooks/", "Payment-provider webhooks, verified by the provider's signature."),
    ("api/v1/payments/", "Payment-provider redirects (Stripe Connect onboarding)."),
    ("api/v1/payment-documents", "Signed one-use payment document links."),
    ("api/v1/wallet/", "Apple Wallet web-service protocol (pass authentication tokens)."),
    ("api/v1/backups/", "One-use backup download tokens."),
    ("api/v1/data-exports/", "One-use data-export download tokens."),
    ("api/v1/recovery", "Deployment recovery gate (operator only)."),
    ("api/v1/internal/", "Infrastructure-only routes, refused at the public edge."),
    ("api/v1/health", "Health and readiness probes."),
    ("api/v1/metrics", "Prometheus metrics: a static bearer token."),
    ("api/v1/oauth/", "OAuth 2.0 / OIDC protocol endpoints: client authentication and PKCE (#196)."),
    ("api/v1/discover/", "Anonymous public discovery of live sites; no client needed."),
    ("control/", "The Django control plane: superadmin session only."),
    ("mfa/", "Control-plane MFA and re-authentication."),
    ("schema/", "The OpenAPI document."),
    ("docs/", "Swagger UI."),
    ("redoc/", "ReDoc."),
    ("api/docs/", "ReDoc (legacy path)."),
    ("embed/", "Anonymous embeddable widgets."),
    ("share/", "Anonymous share pages for crawlers."),
    ("sitemap.xml", "Crawler sitemap."),
    ("robots.txt", "Crawler policy."),
    (".well-known/", "Mobile app association files."),
)
#: The bare root route (`""`) is the docs landing redirect.
ROOT_ROUTE = ""


def out_of_scope_reason(route):
    for prefix, reason in OUT_OF_SCOPE:
        if route.startswith(prefix):
            return reason
    return "The docs landing redirect." if route == ROOT_ROUTE else None


def unclassified_routes():
    """Routes neither under a protected prefix nor listed as deliberately out of scope."""
    from django.urls import get_resolver
    from .scope_registry import _protected_prefixes, _urlconf_routes
    prefixes = _protected_prefixes()
    return sorted({
        (route, view_name)
        for route, view_name, _methods in _urlconf_routes(get_resolver().url_patterns)
        if not route.startswith(prefixes) and out_of_scope_reason(route) is None
    }, key=lambda item: (item[0], item[1] or ""))
