"""Privacy headers for confirmation/scanner successes and pre-view refusals,
and no-store for the anonymous public website reads."""
import re
from django.utils.cache import patch_vary_headers

_PRIVATE_PATH = re.compile(
    r"^/api/v1/(?:public/[^/]+/my-bookings/[0-9a-fA-F-]+/"
    r"(?:confirmation/|confirmation\.png|calendar\.ics|pass\.pdf|rotate-checkin/)|"
    r"admin/spaces/[0-9]+/(?:pass-template/|pass-preview/|arrival/(?:resolve/|confirm/|[0-9]+/(?:reverse/|pass/))))$"
)


def private_response(response):
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    patch_vary_headers(response, ("Authorization", "Cookie"))
    response["X-Content-Type-Options"] = "nosniff"
    return response


# Anonymous booking/event website reads are never cached, success or error. Set here,
# not in a view finalize_response override: that is a pre-auth DRF lifecycle hook the
# claim route guard refuses on a claim-reachable route.
_PUBLIC_NO_STORE_ROUTES = frozenset({
    "public-booking-resource", "public-booking-website", "public-booking-website-image",
    "public-event-website", "public-event-website-section", "public-event-website-speaker",
    "public-event-website-session", "public-event-website-schedule", "public-event-website-image",
})


def private_confirmation_response(request, response):
    # Path matching also covers source-gate/HMAC/auth failures before URL dispatch.
    if _PRIVATE_PATH.fullmatch(request.path_info):
        return private_response(response)
    match = getattr(request, "resolver_match", None)
    if match is not None and match.view_name in _PUBLIC_NO_STORE_ROUTES:
        response["Cache-Control"] = "no-store"
    return response
