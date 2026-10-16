from .claim_route_types import Allowed, AnonymousRead, LocallyFiltered, Refused, SLUG

ROUTES = {("public-presence-now", method): AnonymousRead() for method in ("GET", "HEAD", "OPTIONS")}
for name, methods in (("presence-renew", ("POST",)), ("presence-projects", ("GET", "HEAD"))):
    for method in methods:
        ROUTES[(name, method)] = (Allowed(tenant=SLUG, audited=True) if method == "POST" else LocallyFiltered(tenant=SLUG))
    ROUTES[(name, "OPTIONS")] = AnonymousRead()
for method in ("GET", "HEAD", "PATCH"):
    ROUTES[("presence-preferences", method)] = Refused("Durable display preferences require an ordinary account session.")
ROUTES[("presence-preferences", "OPTIONS")] = AnonymousRead()
