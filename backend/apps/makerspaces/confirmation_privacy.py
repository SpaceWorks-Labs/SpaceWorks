"""Privacy headers for confirmation/scanner successes and pre-view refusals."""
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


def private_confirmation_response(request, response):
    # Path matching also covers source-gate/HMAC/auth failures before URL dispatch.
    if _PRIVATE_PATH.fullmatch(request.path_info):
        return private_response(response)
    return response
