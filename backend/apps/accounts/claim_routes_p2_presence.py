from django.utils.translation import gettext_noop
from .claim_route_types import Allowed, AnonymousRead, LocallyFiltered, Refused, SLUG

ROUTES = {(name, method): AnonymousRead()
          for name in ("public-presence-now", "public-presence-here-now", "public-machines-now",
                     "public-presence-now-config")
          for method in ("GET", "HEAD", "OPTIONS")}
for name, methods in (("presence-renew", ("POST",)), ("presence-projects", ("GET", "HEAD"))):
    for method in methods:
        ROUTES[(name, method)] = (Allowed(tenant=SLUG, audited=True) if method == "POST" else LocallyFiltered(tenant=SLUG))
    ROUTES[(name, "OPTIONS")] = AnonymousRead()
for method in ("GET", "HEAD", "PATCH"):
    ROUTES[("presence-preferences", method)] = Refused(gettext_noop("Durable display preferences require an ordinary account session."))
ROUTES[("presence-preferences", "OPTIONS")] = AnonymousRead()
