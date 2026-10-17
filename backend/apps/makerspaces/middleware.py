from django.http import HttpResponseBadRequest
from django.utils.cache import patch_vary_headers

from apps.makerspaces import domain_verification, hosting


class TenantHostValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not domain_verification.is_self_host():
            raw_host = request.META.get("HTTP_HOST", "")
            if not hosting.host_is_allowed(raw_host):
                return self.profile_headers(request, HttpResponseBadRequest("Invalid host."))
        return self.profile_headers(request, self.get_response(request))

    @staticmethod
    def profile_headers(request, response):
        # Response-only privacy policy also covers pre-handler auth/throttle errors.
        # This middleware neither authenticates nor dispatches claim sessions.
        if request.path_info.startswith(("/api/v1/public/profiles/", "/share/profiles/")):
            response["Cache-Control"] = "no-store"
            patch_vary_headers(response, ("Origin", "Host"))
        return response
