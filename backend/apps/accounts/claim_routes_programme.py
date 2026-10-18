"""Programme claim policy: public metadata only; personal work requires a full login."""
from .claim_route_types import AnonymousRead, Refused
from .programme_route_catalog import ROUTES


CLAIM_ROUTES = {
    (name, method): (AnonymousRead() if name.startswith("events-programme-public-")
                    and name != "events-programme-public-context"
                    and method in {"GET", "HEAD"}
                    else Refused("A full authenticated account is required for programme and saved-detail work."))
    for name, methods, target in ROUTES
    if name.startswith(("events-programme-member-", "events-programme-public-", "member-"))
    for method in methods
}
