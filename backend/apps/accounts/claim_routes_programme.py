"""Programme claim policy: public metadata only; personal work requires a full login."""
from django.utils.translation import gettext_lazy
from .claim_route_types import AnonymousRead, Refused
from .programme_route_catalog import ROUTES


_CLAIM_SURFACE = ("events-programme-member-", "events-programme-public-", "member-")

CLAIM_ROUTES = {
    **{(name, method): (AnonymousRead() if name.startswith("events-programme-public-")
                        and name != "events-programme-public-context"
                        and method in {"GET", "HEAD"}
                        else Refused(gettext_lazy("A full authenticated account is required for programme and saved-detail work.")))
       for name, methods, target in ROUTES if name.startswith(_CLAIM_SURFACE) for method in methods},
    # OPTIONS stays an anonymous CORS preflight, as on every other member route.
    **{(name, "OPTIONS"): AnonymousRead() for name, methods, target in ROUTES if name.startswith(_CLAIM_SURFACE)},
}
